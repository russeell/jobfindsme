from __future__ import annotations

from jobfindsme.doctor import Doctor


def test_doctor_checks_every_operational_layer(tmp_path) -> None:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    report = Doctor(private / "jobfindsme.db").run()

    assert report.ok is True
    assert {item.name for item in report.diagnostics} == {
        "python",
        "database",
        "permissions",
        "mcp",
        "connectors",
        "secrets",
    }
    assert all(item.message for item in report.diagnostics)


def test_doctor_reports_insecure_data_directory_permissions(tmp_path) -> None:
    public = tmp_path / "public"
    public.mkdir(mode=0o755)

    report = Doctor(public / "jobfindsme.db").run()
    permissions = next(
        item for item in report.diagnostics if item.name == "permissions"
    )

    assert report.ok is False
    assert permissions.ok is False
    assert "mode=755" in permissions.message
