from __future__ import annotations

import hashlib
import json
import os
import plistlib
import signal
import stat
import sys
import time
import uuid
import zipfile

import pytest

from jobfindsme import desktop_update as updater


def package_files(platform, version="2.0.0", executable=b"fixture"):
    root = "JobFindsMe.app" if platform == "darwin" else "JobFindsMe"
    resources = "Contents/Resources" if platform == "darwin" else "resources"
    executable_name = (
        "Contents/MacOS/JobFindsMe" if platform == "darwin" else "JobFindsMe.exe"
    )
    files = {
        f"{root}/{resources}/app/package.json": json.dumps(
            {
                "name": "jobfindsme-desktop",
                "version": version,
                "build": f"v{version}",
                "releaseTag": f"v{version}",
                "sourceCommit": "a" * 40,
            }
        ).encode(),
        f"{root}/{resources}/app/dist/index.html": b"fictional UI",
        f"{root}/{resources}/app/dist-electron/main/index.js": b"fictional code",
        f"{root}/{executable_name}": executable,
    }
    if platform == "darwin":
        files[f"{root}/Contents/Info.plist"] = plistlib.dumps(
            {"CFBundleIdentifier": "com.jobfindsme.desktop"}
        )
    return files


def transaction(tmp_path, platform="darwin", executable=b"fixture"):
    tmp_path = tmp_path.resolve()
    root = tmp_path / "安装 directory with 'quotes'" / "JobFindsMe.app"
    if platform == "win32":
        root = root.with_name("JobFindsMe")
    for name, data in package_files(platform, "1.0.0").items():
        file = root / name.split("/", 1)[1]
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
    job = tmp_path / "private cache" / str(uuid.uuid4())
    job.mkdir(parents=True)
    with zipfile.ZipFile(job / "update.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in package_files(platform, executable=executable).items():
            item = zipfile.ZipInfo(name)
            item.external_attr = (stat.S_IFREG | 0o755) << 16
            archive.writestr(item, data)
    request = {
        "schema": 1,
        "id": job.name,
        "job": str(job),
        "platform": platform,
        "version": "v2.0.0",
        "currentVersion": "v1.0.0",
        "sha256": hashlib.sha256((job / "update.zip").read_bytes()).hexdigest(),
        "token": "b" * 64,
        "parentPid": os.getpid(),
        "target": str(root),
        "restartArgs": [],
    }
    updater.write_json(job / "request.json", request)
    return updater.load_transaction(job / "request.json")


@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_prepare_keeps_existing_install_and_user_materials(tmp_path, platform):
    request = transaction(tmp_path, platform)
    private = tmp_path / "user-data"
    private.mkdir()
    for name in ["resume.pdf", "draft.json", "Cookies", "data.sqlite3"]:
        (private / name).write_bytes(b"Fictional local-only material")
    before = {p.name: p.read_bytes() for p in private.iterdir()}
    updater.prepare(request)
    assert updater.app_manifest(request["target_path"], platform)["version"] == "1.0.0"
    assert updater.read_json(request["job_path"] / "state.json")["phase"] == "ready"
    assert {p.name: p.read_bytes() for p in private.iterdir()} == before
    (request["job_path"] / "update.zip").write_bytes(b"changed after preparation")
    with pytest.raises(ValueError, match="checksum"):
        updater.install(request)
    assert request["target_path"].exists()
    assert not request["backup_path"].exists()


@pytest.mark.parametrize(
    "name",
    [
        "../outside",
        "/absolute",
        "JobFindsMe/../../outside",
        "JobFindsMe/drive:C",
        "JobFindsMe/back\\slash",
        "JobFindsMe/null\0suffix",
        "JobFindsMe/CON.txt",
        "JobFindsMe/file. ",
    ],
)
def test_unsafe_zip_paths_do_not_write_outside_staging(tmp_path, name):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        # ZipInfo normalizes backslashes while writing on Windows. Construct
        # the actual malformed central/local header instead of a safe path.
        bundle.writestr(name.replace("\\", "^").replace("\0", "~"), b"fictional")
    if "\\" in name or "\0" in name:
        archive.write_bytes(
            archive.read_bytes().replace(
                name.replace("\\", "^").replace("\0", "~").encode(), name.encode()
            )
        )
    staging = tmp_path / "staging"
    staging.mkdir()
    with pytest.raises(ValueError):
        updater.extract_archive(archive, staging, "win32")
    assert not list(staging.iterdir())


def test_duplicate_case_and_wrong_version_are_rejected(tmp_path):
    request = transaction(tmp_path)
    with zipfile.ZipFile(request["job_path"] / "update.zip", "a") as bundle:
        bundle.writestr("JobFindsMe.app/contents/Info.plist", b"duplicate case")
    request["sha256"] = hashlib.sha256(
        (request["job_path"] / "update.zip").read_bytes()
    ).hexdigest()
    with pytest.raises(ValueError, match="Duplicate"):
        updater.prepare(request)
    assert not request["staging_path"].exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows ZIP distributions reject symlinks")
def test_link_chain_cannot_escape_or_write_through_alias(tmp_path):
    archive = tmp_path / "links.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for name, target in [("x", "."), ("a", "x/..")]:
            item = zipfile.ZipInfo(f"JobFindsMe.app/{name}")
            item.external_attr = (stat.S_IFLNK | 0o777) << 16
            bundle.writestr(item, target)
    staging = tmp_path / "stage"
    staging.mkdir()
    with pytest.raises(ValueError, match="chain escapes"):
        updater.extract_archive(archive, staging, "darwin")


def test_running_parent_never_gets_replaced_and_only_one_guardian(tmp_path):
    request = transaction(tmp_path, "win32")
    with updater.installation_lock(request):
        with pytest.raises(OSError), updater.installation_lock(request):
            pytest.fail("A second guardian acquired the lock")
        updater.install(request, parent_timeout=0)
    assert updater.app_manifest(request["target_path"], "win32")["version"] == "1.0.0"
    assert (
        updater.read_json(request["job_path"] / "state.json")["reason"]
        == "parent_running"
    )


@pytest.mark.skipif(
    os.name == "nt", reason="Actual Windows executable covered by package smoke"
)
@pytest.mark.parametrize("healthy", ["ready", "crash", "wrong_receipt"])
def test_real_child_startup_success_or_failure_rolls_back(
    tmp_path, monkeypatch, healthy
):
    code = f"#!{sys.executable}\n"
    if healthy != "crash":
        code += (
            "import json,os,pathlib,time\n"
            "p=pathlib.Path(os.environ['JFM_UPDATE_MANIFEST']);r=json.loads(p.read_text())\n"
            "(p.parent/'health.json').write_text(json.dumps(dict(id=r['id'],token=r['token'],version=r['version'],pid=os.getpid())))\n"
            "time.sleep(10)\n"
        )
        if healthy == "wrong_receipt":
            code = code.replace("token=r['token']", "token='incorrect-token'")
    else:
        code += "raise SystemExit(1)\n"
    request = transaction(tmp_path, executable=code.encode())
    marker = tmp_path / "old-restarted"
    old_exe = request["target_path"] / "Contents/MacOS/JobFindsMe"
    old_exe.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('old app')\n"
    )
    old_exe.chmod(0o755)
    monkeypatch.setattr(updater, "process_alive", lambda pid: False)
    updater.install(request, health_timeout=4)
    state = updater.read_json(request["job_path"] / "state.json")["phase"]
    assert state == ("installed" if healthy == "ready" else "rolled_back")
    if healthy == "ready":
        receipt = updater.read_json(request["job_path"] / "health.json")
        os.kill(receipt["pid"], signal.SIGTERM)
        os.waitpid(receipt["pid"], 0)
        assert (
            updater.app_manifest(request["target_path"], "darwin")["version"] == "2.0.0"
        )
        assert (
            updater.app_manifest(request["backup_path"], "darwin")["version"] == "1.0.0"
        )
    else:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert marker.read_text() == "old app"
        assert (
            updater.app_manifest(request["target_path"], "darwin")["version"] == "1.0.0"
        )


@pytest.mark.parametrize("failure_point", ["old", "new"])
def test_failure_between_renames_restores_old_program(
    tmp_path, monkeypatch, failure_point
):
    request = transaction(tmp_path, "win32")
    real_rename = updater.rename_retry

    def fail_new(source, target):
        if (
            failure_point == "new"
            and source.parent == request["staging_path"]
            and source.name == "JobFindsMe"
        ) or (failure_point == "old" and source == request["target_path"]):
            raise PermissionError("fictional file lock")
        real_rename(source, target)

    monkeypatch.setattr(updater, "rename_retry", fail_new)
    monkeypatch.setattr(updater, "process_alive", lambda pid: False)
    restarted = []
    from types import SimpleNamespace

    def launch(request, updated):
        restarted.append(updated)
        return SimpleNamespace(pid=1)

    monkeypatch.setattr(updater, "launch", launch)
    updater.install(request)
    assert restarted == [False]
    assert updater.app_manifest(request["target_path"], "win32")["version"] == "1.0.0"
    assert (
        updater.read_json(request["job_path"] / "state.json")["phase"] == "rolled_back"
    )
