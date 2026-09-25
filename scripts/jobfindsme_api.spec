from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata
from pathlib import Path

datas = collect_data_files(
    "jobfindsme", includes=["migrations/*.sql", "resources/**/*"]
)
datas += copy_metadata("agent-job-search")
hiddenimports = collect_submodules("uvicorn")
hiddenimports += ["h11"]
project_root = Path(SPECPATH).parent
datas += [(str(path), "jobfindsme/migrations") for path in
          (project_root / "src/jobfindsme/migrations").glob("*.sql")]

analysis = Analysis(
    [str(project_root / "src/jobfindsme/desktop_api/__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "ruff"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    name="jobfindsme-api",
    exclude_binaries=True,
    console=True,
    strip=False,
    upx=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collection = COLLECT(executable, analysis.binaries, analysis.datas, strip=False, upx=False, name="jobfindsme-api")
