"""Local, offline installer for the desktop ZIP distribution.

Runs from a copied frozen runtime, outside either app directory. Only program
directories and the private update transaction are touched; never user profiles.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import time
import unicodedata
import zipfile
from contextlib import contextmanager, suppress
from pathlib import Path, PurePosixPath

MAX_UNPACKED = 3_000_000_000
MAX_FILES = 30_000


def write_json(file: Path, value: dict) -> None:
    temporary = file.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, file)


def read_json(file: Path) -> dict:
    value = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Invalid update record")
    return value


def app_manifest(root: Path, platform: str) -> dict:
    resources = "Contents/Resources" if platform == "darwin" else "resources"
    return read_json(root / resources / "app/package.json")


def load_transaction(file: Path) -> dict:
    job = file.resolve().parent
    request = read_json(file)
    if (
        request.get("schema") != 1
        or request.get("platform") not in {"darwin", "win32"}
        or not re.fullmatch(r"[a-f0-9-]{36}", request.get("id", ""))
        or not re.fullmatch(r"v\d+\.\d+\.\d+", request.get("version", ""))
        or not re.fullmatch(r"v\d+\.\d+\.\d+", request.get("currentVersion", ""))
        or not re.fullmatch(r"[a-f0-9]{64}", request.get("sha256", ""))
        or not re.fullmatch(r"[a-f0-9]{64}", request.get("token", ""))
        or request.get("job") != str(job)
        or not isinstance(request.get("parentPid"), int)
        or request["parentPid"] < 2
        or not isinstance(request.get("restartArgs", []), list)
        or len(request.get("restartArgs", [])) > 1
        or any(
            not isinstance(arg, str)
            or not arg.startswith("--user-data-dir=")
            or not Path(arg.split("=", 1)[1]).is_absolute()
            for arg in request.get("restartArgs", [])
        )
    ):
        raise ValueError("Invalid update transaction")
    target = Path(request["target"])
    if not target.is_absolute() or target.is_symlink() or target.resolve() != target:
        raise ValueError("Update target must be a real installation directory")
    if job == target or job.is_relative_to(target) or target.is_relative_to(job):
        raise ValueError("Update transaction must be outside the application")
    expected = app_manifest(target, request["platform"])
    if expected.get("name") != "jobfindsme-desktop":
        raise ValueError("Not a JobFindsMe installation")
    if f"v{expected.get('version')}" != request["currentVersion"]:
        raise ValueError("The installed version changed")
    if tuple(map(int, request["version"][1:].split("."))) <= tuple(
        map(int, request["currentVersion"][1:].split("."))
    ):
        raise ValueError("Update must be a newer version")
    request.update(
        job_path=job,
        target_path=target,
        staging_path=target.parent / f".jobfindsme-stage-{request['id']}",
        backup_path=target.parent / f".jobfindsme-backup-{request['id']}",
    )
    return request


def record(request: dict, phase: str, **extra) -> None:
    write_json(
        request["job_path"] / "state.json",
        {"phase": phase, "version": request["version"], "id": request["id"], **extra},
    )


def verify_archive(request: dict) -> Path:
    archive = request["job_path"] / "update.zip"
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != request["sha256"]:
        raise ValueError("Update checksum mismatch")
    return archive


def extract_archive(archive: Path, destination: Path, platform: str) -> Path:
    """Preflight every member; write regular files before contained symlinks."""
    root_name = "JobFindsMe.app" if platform == "darwin" else "JobFindsMe"
    seen: set[str] = set()
    entries = []
    links = []
    with zipfile.ZipFile(archive) as bundle:
        if len(bundle.infolist()) > MAX_FILES:
            raise ValueError("Too many update files")
        total = 0
        for item in bundle.infolist():
            # ZipInfo normalizes Windows separators and truncates at NUL.
            # Check the original header before trusting the normalized path.
            name = item.orig_filename
            parts = tuple(name.rstrip("/").split("/"))
            if (
                not parts
                or name.startswith("/")
                or "\\" in name
                or any(p in {".", ".."} or ":" in p or "\0" in p for p in parts)
                or any(p.endswith((" ", ".")) for p in parts)
                or any(not p for p in parts)
                or platform == "win32"
                and any(
                    re.fullmatch(
                        r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", p, re.I
                    )
                    or re.search(r'[<>"|?*]', p)
                    for p in parts
                )
            ):
                raise ValueError("Unsafe path in update")
            if parts[0] == "__MACOSX" and platform == "darwin":
                continue
            if parts[0] != root_name:
                raise ValueError("Unexpected update root")
            key = unicodedata.normalize("NFC", name.rstrip("/")).casefold()
            if key in seen:
                raise ValueError("Duplicate update path")
            seen.add(key)
            mode = item.external_attr >> 16
            total += item.file_size
            if total > MAX_UNPACKED or item.flag_bits & 1:
                raise ValueError("Unsupported or oversized update")
            if stat.S_ISLNK(mode):
                if platform != "darwin" or item.file_size > 4096:
                    raise ValueError("Unsupported update link")
                link = bundle.read(item).decode("utf-8")
                if "\\" in link or PurePosixPath(link).is_absolute():
                    raise ValueError("Unsafe update link")
                target = (destination / name).parent.joinpath(link).resolve()
                if not target.is_relative_to(destination / root_name):
                    raise ValueError("Update link escapes application")
                links.append((item, link))
            elif item.is_dir() or stat.S_IFMT(mode) in {0, stat.S_IFREG, stat.S_IFDIR}:
                entries.append(item)
            else:
                raise ValueError("Unsupported update file type")
        link_names = {item.filename.rstrip("/") for item, _ in links}
        for item in entries + [item for item, _ in links]:
            if any(
                str(parent) in link_names
                for parent in PurePosixPath(item.filename).parents
            ):
                raise ValueError("Update writes through a link")
        for item in entries:
            output = destination / item.filename
            if item.is_dir():
                output.mkdir(parents=True, exist_ok=True)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(item) as source, output.open("xb") as target:
                    shutil.copyfileobj(source, target)
                output.chmod(0o755 if item.external_attr >> 16 & 0o111 else 0o644)
        for item, link in links:
            output = destination / item.filename
            output.parent.mkdir(parents=True, exist_ok=True)
            output.symlink_to(link)
        for item, _ in links:
            target = (destination / item.filename).resolve(strict=True)
            if not target.is_relative_to(destination / root_name):
                raise ValueError("Update link chain escapes application")
    return destination / root_name


def validate_candidate(candidate: Path, request: dict) -> None:
    manifest = app_manifest(candidate, request["platform"])
    if (
        manifest.get("name") != "jobfindsme-desktop"
        or f"v{manifest.get('version')}" != request["version"]
        or manifest.get("releaseTag") != request["version"]
        or manifest.get("build") != request["version"]
        or manifest.get("jobfindsmePreview")
        or manifest.get("qa")
        or not re.fullmatch(r"[a-f0-9]{40}", manifest.get("sourceCommit", ""))
    ):
        raise ValueError("Update version or identity mismatch")
    executable = candidate / (
        "Contents/MacOS/JobFindsMe"
        if request["platform"] == "darwin"
        else "JobFindsMe.exe"
    )
    if not executable.is_file():
        raise ValueError("Missing update executable")
    resources = "Contents/Resources" if request["platform"] == "darwin" else "resources"
    for file in ["app/dist/index.html", "app/dist-electron/main/index.js"]:
        if not (candidate / resources / file).is_file():
            raise ValueError("Incomplete update")
    if request["platform"] == "darwin":
        import plistlib

        with (candidate / "Contents/Info.plist").open("rb") as source:
            info = plistlib.load(source)
        if info.get("CFBundleIdentifier") != "com.jobfindsme.desktop":
            raise ValueError("Update bundle identity mismatch")


def prepare(request: dict) -> None:
    archive = verify_archive(request)
    staging = request["staging_path"]
    if staging.exists():
        if staging.is_symlink():
            raise ValueError("Unsafe staging directory")
        shutil.rmtree(staging)
    staging.mkdir(mode=0o700)
    try:
        candidate = extract_archive(archive, staging, request["platform"])
        validate_candidate(candidate, request)
        record(request, "ready")
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        record(request, "failed", reason="prepare")
        raise


def process_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(ctypes.c_void_p(handle), 0) == 0x102
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def launch(request: dict, updated: bool) -> subprocess.Popen:
    target = request["target_path"]
    executable = target / (
        "Contents/MacOS/JobFindsMe"
        if request["platform"] == "darwin"
        else "JobFindsMe.exe"
    )
    environment = dict(os.environ)
    for key in list(environment):
        if key.startswith("_PYI_") or key in {
            "_MEIPASS2",
            "PYTHONHOME",
            "PYTHONPATH",
            "JFM_UPDATE_MANIFEST",
        }:
            environment.pop(key, None)
    for key in ["LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"]:
        original = environment.pop(f"{key}_ORIG", None)
        environment.pop(key, None)
        if original:
            environment[key] = original
    environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    if updated:
        environment["JFM_UPDATE_MANIFEST"] = str(request["job_path"] / "request.json")
    if os.name == "nt":
        import ctypes

        ctypes.windll.kernel32.SetDllDirectoryW(None)
    child = subprocess.Popen(
        [str(executable), *request.get("restartArgs", [])],
        cwd=target.parent,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name != "nt",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    if updated and os.name == "nt" and child.poll() is None:
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.restype = ctypes.c_void_p
        kernel.OpenProcess.restype = ctypes.c_void_p
        job = kernel.CreateJobObjectW(None, None)
        process = kernel.OpenProcess(0x0100 | 0x0001 | 0x0400, False, child.pid)
        if (
            job
            and process
            and kernel.AssignProcessToJobObject(
                ctypes.c_void_p(job), ctypes.c_void_p(process)
            )
        ):
            child.update_job = job
        elif job:
            kernel.CloseHandle(ctypes.c_void_p(job))
        if process:
            kernel.CloseHandle(ctypes.c_void_p(process))
    return child


def stop_candidate(child: subprocess.Popen) -> None:
    if os.name == "nt":
        if getattr(child, "update_job", None):
            import ctypes

            ctypes.windll.kernel32.TerminateJobObject(
                ctypes.c_void_p(child.update_job), 1
            )
        elif child.poll() is None:
            subprocess.run(
                ["taskkill.exe", "/PID", str(child.pid), "/T", "/F"],
                capture_output=True,
                timeout=15,
                check=False,
            )
    else:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        child.wait(timeout=8)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            os.killpg(child.pid, signal.SIGKILL)
        else:
            child.kill()
        child.wait(timeout=5)


def rename_retry(source: Path, target: Path) -> None:
    for attempt in range(40):
        try:
            source.rename(target)
            return
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(0.25)


def install(
    request: dict, *, parent_timeout: float = 90, health_timeout: float = 90
) -> None:
    # Re-extract and re-verify immediately before accepting the parent's exit.
    prepare(request)
    record(request, "waiting", guardian_pid=os.getpid())
    print(json.dumps({"event": "waiting"}), flush=True)
    deadline = time.monotonic() + parent_timeout
    while process_alive(request["parentPid"]):
        if time.monotonic() > deadline:
            record(request, "failed", reason="parent_running")
            return
        time.sleep(0.15)
    target, backup = request["target_path"], request["backup_path"]
    candidate = request["staging_path"] / (
        "JobFindsMe.app" if request["platform"] == "darwin" else "JobFindsMe"
    )
    child = None
    old_moved = False
    try:
        if backup.exists():
            raise ValueError("Backup already exists")
        record(request, "installing", guardian_pid=os.getpid())
        rename_retry(target, backup)
        old_moved = True
        rename_retry(candidate, target)
        record(request, "starting", guardian_pid=os.getpid())
        child = launch(request, True)
        deadline = time.monotonic() + health_timeout
        healthy_at = None
        while time.monotonic() < deadline and child.poll() is None:
            try:
                receipt = read_json(request["job_path"] / "health.json")
                healthy = receipt == {
                    "id": request["id"],
                    "token": request["token"],
                    "version": request["version"],
                    "pid": child.pid,
                }
            except (OSError, ValueError):
                healthy = False
            if healthy:
                healthy_at = healthy_at or time.monotonic()
                if time.monotonic() - healthy_at >= 2:
                    record(request, "installed")
                    shutil.rmtree(request["staging_path"], ignore_errors=True)
                    return
            else:
                healthy_at = None
            time.sleep(0.15)
        raise RuntimeError("New application did not become ready")
    except Exception:
        if child:
            with suppress(OSError, subprocess.TimeoutExpired):
                stop_candidate(child)
        if old_moved:
            if target.exists():
                rename_retry(target, request["staging_path"] / "failed-app")
            rename_retry(backup, target)
            try:
                record(request, "rolled_back", reason="startup_or_install")
            finally:
                restarted = launch(request, False)
                record(
                    request,
                    "rolled_back",
                    reason="startup_or_install",
                    pid=restarted.pid,
                )
        else:
            try:
                record(request, "rolled_back", reason="install_not_replaced")
            finally:
                restarted = launch(request, False)
                record(
                    request,
                    "rolled_back",
                    reason="install_not_replaced",
                    pid=restarted.pid,
                )
        # The previous application is kept; no profile/database rollback or
        # deletion. Database migrations must remain backwards compatible.
        shutil.rmtree(request["staging_path"], ignore_errors=True)
    finally:
        if child and getattr(child, "update_job", None):
            import ctypes

            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(child.update_job))


@contextmanager
def installation_lock(request: dict):
    # OS releases this lock if the guardian crashes. Different userData profiles
    # cannot concurrently replace the same application directory.
    with (request["target_path"].parent / ".jobfindsme-update.lock").open(
        "a+b"
    ) as lock:
        lock.seek(0)
        if os.name == "nt":
            import msvcrt

            if lock.read(1) == b"":
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main(args: list[str]) -> int:
    if len(args) != 2 or args[0] not in {"prepare", "install"}:
        return 2
    try:
        request = load_transaction(Path(args[1]))
        with installation_lock(request):
            if args[0] == "prepare":
                prepare(request)
                print(json.dumps({"event": "ready"}), flush=True)
            else:
                install(request)
        return 0
    except Exception:
        # Paths, environment and runtime diagnostics must not enter public logs.
        print(json.dumps({"event": "failed"}), flush=True)
        return 1
