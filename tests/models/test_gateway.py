from __future__ import annotations

from typing import Any

import pytest

from jobfindsme.models import (
    CancellationToken,
    ModelCancelledError,
    ModelConnection,
    ModelConnectionRepository,
    ModelGateway,
    ModelProtocol,
)
from jobfindsme.models.gateway import (
    ConnectionStatus,
    ModelGatewayError,
    TransportResponse,
    UrllibJsonTransport,
)
from jobfindsme.storage import Database


class FakeTransport:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.request: dict[str, Any] | None = None

    def post(self, **kwargs: Any) -> TransportResponse:
        kwargs["cancellation"].raise_if_cancelled()
        self.request = kwargs
        return TransportResponse(status=200, payload=self.response)


@pytest.mark.parametrize(
    ("protocol", "response", "url_part", "expected_usage"),
    [
        (
            ModelProtocol.OPENAI_COMPATIBLE,
            {
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                    "total_tokens": 3,
                },
            },
            "/chat/completions",
            (2, 1),
        ),
        (
            ModelProtocol.ANTHROPIC,
            {
                "content": [{"text": '{"ok": true}'}],
                "usage": {"input_tokens": 3, "output_tokens": 1},
            },
            "/messages",
            (3, 1),
        ),
        (
            ModelProtocol.GEMINI,
            {
                "candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}],
                "usageMetadata": {
                    "promptTokenCount": 4,
                    "candidatesTokenCount": 1,
                    "totalTokenCount": 5,
                },
            },
            ":generateContent",
            (4, 1),
        ),
    ],
)
def test_each_protocol_maps_request_response_and_usage(
    protocol: ModelProtocol,
    response: dict[str, Any],
    url_part: str,
    expected_usage: tuple[int, int],
) -> None:
    transport = FakeTransport(response)
    gateway = ModelGateway(transport)
    connection = ModelConnection(
        connection_id="connection-1",
        provider="test",
        protocol=protocol,
        endpoint="https://model.example/v1",
        model_id="model-1",
        status=ConnectionStatus.UNVERIFIED,
    )

    result = gateway.generate_structured(
        connection=connection,
        api_key="secret-key",
        prompt="test",
        timeout_seconds=3,
    )

    assert result.structured == {"ok": True}
    assert (result.usage.input_tokens, result.usage.output_tokens) == expected_usage
    assert transport.request is not None
    assert url_part in transport.request["url"]
    assert "secret-key" not in transport.request["url"]
    if protocol is ModelProtocol.GEMINI:
        assert transport.request["headers"]["x-goog-api-key"] == "secret-key"
    assert transport.request["timeout_seconds"] == 3
    assert gateway.usage() == result.usage


def test_cancelled_request_never_reaches_transport() -> None:
    transport = FakeTransport({})
    token = CancellationToken()
    token.cancel()
    connection = ModelConnection(
        connection_id="connection-1",
        provider="test",
        protocol=ModelProtocol.OPENAI_COMPATIBLE,
        endpoint="https://model.example/v1",
        model_id="model-1",
    )

    with pytest.raises(ModelCancelledError):
        ModelGateway(transport).generate_structured(
            connection=connection,
            api_key="secret-key",
            prompt="test",
            cancellation=token,
        )
    assert transport.request is None


def test_direct_timeout_is_normalized_without_accessing_reason(monkeypatch) -> None:
    class TimedOutConnection:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def connect(self) -> None:
            raise TimeoutError("timed out")

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        "jobfindsme.models.gateway.http.client.HTTPSConnection",
        TimedOutConnection,
    )
    with pytest.raises(ModelGatewayError, match="model endpoint timed out"):
        UrllibJsonTransport().post(
            url="https://model.example/v1/messages",
            headers={},
            payload={},
            timeout_seconds=1,
            cancellation=CancellationToken(),
        )


def test_stale_model_test_cannot_overwrite_newer_run(tmp_path) -> None:
    repository = ModelConnectionRepository(Database(tmp_path / "models.db"))
    connection = repository.save(
        provider="Example",
        protocol=ModelProtocol.OPENAI_COMPATIBLE,
        endpoint="https://model.example/v1",
        model_id="example-1",
    )
    repository.begin_test(connection_id=connection.connection_id, test_id="old-test")
    repository.begin_test(connection_id=connection.connection_id, test_id="new-test")

    stale = repository.finish_test(
        connection_id=connection.connection_id,
        test_id="old-test",
        status=ConnectionStatus.VERIFIED,
    )
    assert stale.status is ConnectionStatus.TESTING

    current = repository.cancel_test(
        connection_id=connection.connection_id,
        test_id="new-test",
    )
    assert current.status is ConnectionStatus.CANCELLED


def test_routing_change_without_new_key_clears_credential_pairing(tmp_path) -> None:
    repository = ModelConnectionRepository(Database(tmp_path / "models.db"))
    original = repository.save(
        provider="Example",
        protocol=ModelProtocol.OPENAI_COMPATIBLE,
        endpoint="https://old.example/v1",
        model_id="example-1",
        credential_ref="secret-revision-1",
    )
    updated = repository.save(
        connection_id=original.connection_id,
        provider="Example",
        protocol=ModelProtocol.OPENAI_COMPATIBLE,
        endpoint="https://new.example/v1",
        model_id="example-1",
    )
    assert updated.credential_ref is None


@pytest.mark.parametrize("protocol", list(ModelProtocol))
def test_explicit_local_no_auth_omits_all_credentials(protocol):
    from jobfindsme.models.gateway import _request_for

    connection = ModelConnection(
        connection_id="local",
        provider="local",
        protocol=protocol,
        endpoint="http://localhost:1234/v1",
        model_id="installed-model",
        auth_mode="none",
    )
    _, headers, _ = _request_for(connection, "", "test")
    assert not {"Authorization", "x-api-key", "x-goog-api-key"}.intersection(headers)


def test_no_auth_is_explicit_local_only_and_clears_old_reference(tmp_path):
    repo = ModelConnectionRepository(Database(tmp_path / "model.db"))
    original = repo.save(
        provider="local",
        protocol=ModelProtocol.OPENAI_COMPATIBLE,
        endpoint="http://localhost:1234/v1",
        model_id="installed-model",
        credential_ref="encrypted-old",
    )
    changed = repo.save(
        provider="local",
        protocol=original.protocol,
        endpoint=original.endpoint,
        model_id=original.model_id,
        connection_id=original.connection_id,
        auth_mode="none",
        credential_ref="should-not-survive",
    )
    assert changed.auth_mode == "none"
    assert changed.credential_ref is None
    with pytest.raises(ValueError, match="本机"):
        repo.save(
            provider="remote",
            protocol=original.protocol,
            endpoint="https://example.com/v1",
            model_id="model",
            auth_mode="none",
        )
    transport = FakeTransport({"choices": [{"message": {"content": '{"ok":true}'}}]})
    result = ModelGateway(transport).generate_structured(
        connection=changed, api_key="", prompt="test"
    )
    assert result.structured == {"ok": True}
    assert transport.request["headers"] == {}
    with pytest.raises(ModelGatewayError, match="API key"):
        ModelGateway(transport).generate_structured(
            connection=original, api_key="", prompt="test"
        )


def test_local_no_key_uses_real_loopback_http(tmp_path):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    captured = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            captured.append(
                (self.path, self.headers.get("Authorization"), body["model"])
            )
            payload = b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        repo = ModelConnectionRepository(Database(tmp_path / "local.db"))
        connection = repo.save(
            provider="Local test fixture",
            protocol=ModelProtocol.OPENAI_COMPATIBLE,
            endpoint=f"http://127.0.0.1:{server.server_port}/v1",
            model_id="fixture-only",
            auth_mode="none",
        )
        result = ModelGateway().generate_structured(
            connection=connection,
            api_key="",
            prompt="test",
        )
        assert result.structured == {"ok": True}
        assert captured == [("/v1/chat/completions", None, "fixture-only")]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
