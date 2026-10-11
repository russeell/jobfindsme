import pytest

from jobfindsme.desktop_api import runtime_check


def test_network_runtime_performs_real_loopback_request():
    assert runtime_check.check_runtime() == {"curl_http": "ok", "ca_bundle": "ok"}


def test_network_runtime_rejects_missing_transport(monkeypatch):
    def missing():
        raise ImportError("transport missing")

    monkeypatch.setattr(runtime_check, "_default_session_factory", missing)
    with pytest.raises(ImportError, match="transport missing"):
        runtime_check.check_runtime()
