from __future__ import annotations

from jobfindsme.doctor import Doctor


def test_doctor_checks_every_operational_layer(tmp_path) -> None:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    report = Doctor(private / "jobfindsme.db").run()

    assert report.ok is True
    assert {item.name for item in report.diagnostics} == {
        "version",
        "python",
        "database",
        "permissions",
        "mcp",
        "connectors",
        "browser_connectors",
        "boss_login",
        "secrets",
    }
    assert all(item.message for item in report.diagnostics)
    mcp = next(item for item in report.diagnostics if item.name == "mcp")
    assert mcp.message == "10 tools"


def test_missing_optional_browser_dependencies_do_not_fail_core_doctor(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "jobfindsme.doctor.service.find_spec",
        lambda _name: None,
    )

    report = Doctor(tmp_path / "private" / "jobfindsme.db").run()
    browser = next(
        item for item in report.diagnostics if item.name == "browser_connectors"
    )

    assert report.ok is True
    assert browser.ok is False
    assert browser.required is False
    assert "jobfindsme[browser]" in browser.message


def test_missing_browser_binary_is_reported_as_optional(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "jobfindsme.doctor.service.find_spec",
        lambda _name: object(),
    )
    monkeypatch.setattr(
        "jobfindsme.doctor.service._cdp_port_reachable",
        lambda: False,
    )

    report = Doctor(tmp_path / "private" / "jobfindsme.db").run()
    browser = next(
        item for item in report.diagnostics if item.name == "browser_connectors"
    )

    assert report.ok is True
    assert browser.ok is False
    assert "jobfindsme setup" in browser.message


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


def test_boss_login_probe_navigates_to_same_origin_and_closes_resources(
    monkeypatch,
) -> None:
    class FakeCdp:
        def __init__(self) -> None:
            self.calls = []
            self.closed = False

        def send(self, method, params=None, sid=None):
            self.calls.append((method, params or {}, sid))
            if method == "Target.createTarget":
                return {"result": {"targetId": "target-1"}}
            if method == "Target.attachToTarget":
                return {"result": {"sessionId": "session-1"}}
            return {"result": {}}

        def eval_js(self, script, _sid):
            if script == "document.readyState":
                return "complete"
            return '{"jobs":[{"job_id":"job-1"}]}'

        def close(self):
            self.closed = True

    fake = FakeCdp()
    monkeypatch.setattr(
        "jobfindsme.doctor.service._cdp_port_reachable",
        lambda: True,
    )
    monkeypatch.setattr(
        "jobfindsme.connectors.boss_zhipin._CDPSession",
        lambda _port: fake,
    )

    diagnostic = Doctor._boss_login()

    methods = [method for method, _, _ in fake.calls]
    navigate = next(call for call in fake.calls if call[0] == "Page.navigate")
    assert diagnostic.ok is True
    assert navigate[1]["url"].startswith("https://www.zhipin.com/")
    assert methods[-1] == "Target.closeTarget"
    assert fake.closed is True


def test_empty_boss_probe_is_not_misreported_as_logged_out(monkeypatch) -> None:
    monkeypatch.setattr(
        "jobfindsme.doctor.service._cdp_port_reachable",
        lambda: True,
    )
    monkeypatch.setattr(
        "jobfindsme.connectors.boss_zhipin.BossZhipinConnector.fetch",
        lambda _self: [],
    )

    diagnostic = Doctor._boss_login()

    assert diagnostic.ok is True
    assert "限流" in diagnostic.message
    assert "需要登录" not in diagnostic.message
