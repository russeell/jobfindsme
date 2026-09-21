from __future__ import annotations

import http.client
import json
import threading
import urllib.parse
from collections.abc import Iterator, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, Protocol
from urllib.parse import urlparse
from uuid import uuid4

from pydantic import Field

from jobfindsme.contracts import StrictModel
from jobfindsme.storage import Database


class ModelProtocol(StrEnum):
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class ConnectionStatus(StrEnum):
    UNVERIFIED = "unverified"
    TESTING = "testing"
    VERIFIED = "verified"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ModelConnection(StrictModel):
    connection_id: str
    provider: str = Field(min_length=1, max_length=80)
    protocol: ModelProtocol
    endpoint: str
    model_id: str = Field(min_length=1, max_length=160)
    status: ConnectionStatus = ConnectionStatus.UNVERIFIED
    last_error: str | None = None
    last_tested_at: datetime | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    credential_ref: str | None = None
    auth_mode: Literal["api_key", "none"] = "api_key"


class ModelUsage(StrictModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ModelResult(StrictModel):
    text: str
    structured: dict[str, Any] | None = None
    usage: ModelUsage


class ModelGatewayError(RuntimeError):
    pass


class ModelCancelledError(ModelGatewayError):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._callbacks: list[Any] = []

    def cancel(self) -> None:
        with self._lock:
            self._event.set()
            callbacks = tuple(self._callbacks)
        for callback in callbacks:
            with suppress(OSError):
                callback()

    def register(self, callback: Any) -> None:
        with self._lock:
            if self._event.is_set():
                run_now = True
            else:
                self._callbacks.append(callback)
                run_now = False
        if run_now:
            callback()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise ModelCancelledError("model request was cancelled")


@dataclass(frozen=True)
class TransportResponse:
    status: int
    payload: Mapping[str, Any]


class JsonTransport(Protocol):
    def post(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
        cancellation: CancellationToken,
    ) -> TransportResponse: ...


class UrllibJsonTransport:
    def post(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
        cancellation: CancellationToken,
    ) -> TransportResponse:
        cancellation.raise_if_cancelled()
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ModelGatewayError("model endpoint URL is invalid")
        connection_type = (
            http.client.HTTPSConnection
            if parsed.scheme == "https"
            else http.client.HTTPConnection
        )
        connection = connection_type(
            parsed.hostname,
            parsed.port,
            timeout=timeout_seconds,
        )
        cancellation.register(connection.close)
        path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        try:
            cancellation.raise_if_cancelled()
            connection.connect()
            cancellation.raise_if_cancelled()
            connection.request(
                "POST",
                path,
                body=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", **headers},
            )
            response = connection.getresponse()
            body = response.read()
            status = response.status
        except TimeoutError as error:
            cancellation.raise_if_cancelled()
            raise ModelGatewayError("model endpoint timed out") from error
        except (OSError, http.client.HTTPException) as error:
            cancellation.raise_if_cancelled()
            raise ModelGatewayError("model endpoint unavailable") from error
        finally:
            connection.close()
        cancellation.raise_if_cancelled()
        if status >= 400:
            raise ModelGatewayError(f"model endpoint returned HTTP {status}")
        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as error:
            raise ModelGatewayError("model endpoint returned invalid JSON") from error
        if not isinstance(decoded, dict):
            raise ModelGatewayError("model endpoint returned an invalid payload")
        return TransportResponse(status=status, payload=decoded)


class ModelGateway:
    def __init__(self, transport: JsonTransport | None = None) -> None:
        self.transport = transport or UrllibJsonTransport()
        self._last_usage = ModelUsage()

    def generate_structured(
        self,
        *,
        connection: ModelConnection,
        api_key: str,
        prompt: str,
        timeout_seconds: float = 20,
        max_output_tokens: int = 2000,
        cancellation: CancellationToken | None = None,
    ) -> ModelResult:
        _validate_auth(connection.endpoint, connection.auth_mode)
        if connection.auth_mode == "none":
            api_key = ""
        elif not api_key.strip():
            raise ModelGatewayError("API key is required")
        if not 1 <= timeout_seconds <= 120:
            raise ModelGatewayError("timeout must be between 1 and 120 seconds")
        token = cancellation or CancellationToken()
        token.raise_if_cancelled()
        if not 1 <= max_output_tokens <= 8000:
            raise ModelGatewayError("output budget must be between 1 and 8000 tokens")
        url, headers, payload = _request_for(connection, api_key, prompt)
        if connection.protocol is ModelProtocol.GEMINI:
            payload["generationConfig"] = {"maxOutputTokens": max_output_tokens}
        else:
            payload["max_tokens"] = max_output_tokens
        response = self.transport.post(
            url=url,
            headers=headers,
            payload=payload,
            timeout_seconds=timeout_seconds,
            cancellation=token,
        )
        text, usage = _response_for(connection.protocol, response.payload)
        structured = None
        try:
            value = json.loads(text)
            if isinstance(value, dict):
                structured = value
        except json.JSONDecodeError:
            pass
        self._last_usage = usage
        return ModelResult(text=text, structured=structured, usage=usage)

    def stream(self, **kwargs: Any) -> Iterator[str]:
        """Unified bounded stream contract; adapters may yield one complete chunk."""

        yield self.generate_structured(**kwargs).text

    @staticmethod
    def cancel(cancellation: CancellationToken) -> None:
        cancellation.cancel()

    def usage(self) -> ModelUsage:
        return self._last_usage


class ModelConnectionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save(
        self,
        *,
        provider: str,
        protocol: ModelProtocol,
        endpoint: str,
        model_id: str,
        connection_id: str | None = None,
        credential_ref: str | None = None,
        auth_mode: Literal["api_key", "none"] = "api_key",
    ) -> ModelConnection:
        self.database.migrate()
        normalized_endpoint = _validate_endpoint(endpoint)
        _validate_auth(normalized_endpoint, auth_mode)
        if auth_mode == "none":
            credential_ref = None
        now = datetime.now(UTC).isoformat()
        identifier = connection_id or f"model_connection_{uuid4().hex}"
        with self.database.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM model_connections WHERE connection_id = ?",
                (identifier,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO model_connections (
                        connection_id, provider, protocol, endpoint, model_id,
                        status, created_at, updated_at, credential_ref, auth_mode
                    ) VALUES (?, ?, ?, ?, ?, 'unverified', ?, ?, ?, ?)
                    """,
                    (
                        identifier,
                        provider.strip(),
                        protocol.value,
                        normalized_endpoint,
                        model_id.strip(),
                        now,
                        now,
                        credential_ref,
                        auth_mode,
                    ),
                )
            else:
                routing_changed = any(
                    (
                        existing["auth_mode"] != auth_mode,
                        existing["provider"] != provider.strip(),
                        existing["protocol"] != protocol.value,
                        existing["endpoint"] != normalized_endpoint,
                        existing["model_id"] != model_id.strip(),
                    )
                )
                next_credential_ref = (
                    credential_ref
                    if credential_ref is not None
                    else None
                    if routing_changed
                    else existing["credential_ref"]
                )
                connection.execute(
                    """
                    UPDATE model_connections
                    SET provider = ?, protocol = ?, endpoint = ?, model_id = ?,
                        status = 'unverified', last_error = NULL,
                        last_tested_at = NULL, input_tokens = NULL,
                        output_tokens = NULL, credential_ref = ?, updated_at = ?,
                        auth_mode = ?
                    WHERE connection_id = ?
                    """,
                    (
                        provider.strip(),
                        protocol.value,
                        normalized_endpoint,
                        model_id.strip(),
                        next_credential_ref,
                        now,
                        auth_mode,
                        identifier,
                    ),
                )
        return self.get(identifier)

    def begin_test(self, *, connection_id: str, test_id: str) -> ModelConnection:
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as connection:
            if (
                connection.execute(
                    "SELECT 1 FROM model_connections WHERE connection_id = ?",
                    (connection_id,),
                ).fetchone()
                is None
            ):
                raise LookupError(connection_id)
            connection.execute(
                """
                UPDATE model_test_runs
                SET status = 'cancelled', finished_at = ?
                WHERE connection_id = ? AND status = 'testing'
                """,
                (now, connection_id),
            )
            connection.execute(
                """
                INSERT INTO model_test_runs (
                    test_id, connection_id, status, started_at
                ) VALUES (?, ?, 'testing', ?)
                """,
                (test_id, connection_id, now),
            )
            connection.execute(
                """
                UPDATE model_connections
                SET status = 'testing', last_error = NULL, updated_at = ?
                WHERE connection_id = ?
                """,
                (now, connection_id),
            )
        return self.get(connection_id)

    def finish_test(
        self,
        *,
        connection_id: str,
        test_id: str,
        status: ConnectionStatus,
        usage: ModelUsage | None = None,
        error: str | None = None,
    ) -> ModelConnection:
        if status is ConnectionStatus.TESTING:
            raise ValueError("test cannot finish with testing status")
        finished_at = datetime.now(UTC).isoformat()
        with self.database.connect() as connection:
            changed = connection.execute(
                """
                UPDATE model_test_runs
                SET status = ?, finished_at = ?
                WHERE test_id = ? AND connection_id = ? AND status = 'testing'
                """,
                (status.value, finished_at, test_id, connection_id),
            ).rowcount
            if changed:
                connection.execute(
                    """
                    UPDATE model_connections
                    SET status = ?, last_error = ?, last_tested_at = ?,
                        input_tokens = ?, output_tokens = ?, updated_at = ?
                    WHERE connection_id = ?
                      AND NOT EXISTS (
                        SELECT 1 FROM model_test_runs
                        WHERE connection_id = ? AND status = 'testing'
                      )
                    """,
                    (
                        status.value,
                        error[:500] if error else None,
                        finished_at,
                        usage.input_tokens if usage else None,
                        usage.output_tokens if usage else None,
                        finished_at,
                        connection_id,
                        connection_id,
                    ),
                )
        return self.get(connection_id)

    def cancel_test(self, *, connection_id: str, test_id: str) -> ModelConnection:
        return self.finish_test(
            connection_id=connection_id,
            test_id=test_id,
            status=ConnectionStatus.CANCELLED,
            error="connection test cancelled",
        )

    def list(self) -> list[ModelConnection]:
        self.database.migrate()
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_connections ORDER BY updated_at DESC"
            ).fetchall()
        return [_connection_from_row(row) for row in rows]

    def get(self, connection_id: str) -> ModelConnection:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM model_connections WHERE connection_id = ?",
                (connection_id,),
            ).fetchone()
        if row is None:
            raise LookupError(connection_id)
        return _connection_from_row(row)


def _validate_auth(endpoint: str, auth_mode: str) -> None:
    _validate_endpoint(endpoint)
    if auth_mode not in {"api_key", "none"}:
        raise ValueError("unsupported authentication mode")
    if auth_mode == "none" and urlparse(endpoint).hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("免密模式仅支持本机模型服务")


def _validate_endpoint(endpoint: str) -> str:
    value = endpoint.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("endpoint must be an absolute HTTP(S) URL")
    if parsed.query or parsed.fragment:
        raise ValueError("endpoint must not contain query or fragment")
    if parsed.username or parsed.password:
        raise ValueError("endpoint must not contain credentials")
    if parsed.scheme != "https" and parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise ValueError("non-local model endpoints must use HTTPS")
    return value


def _request_for(
    connection: ModelConnection, api_key: str, prompt: str
) -> tuple[str, dict[str, str], dict[str, Any]]:
    endpoint = connection.endpoint.rstrip("/")
    if connection.protocol is ModelProtocol.OPENAI_COMPATIBLE:
        return (
            f"{endpoint}/chat/completions",
            ({"Authorization": f"Bearer {api_key}"} if api_key else {}),
            {
                "model": connection.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
                "temperature": 0,
            },
        )
    if connection.protocol is ModelProtocol.ANTHROPIC:
        return (
            f"{endpoint}/messages",
            {
                **({"x-api-key": api_key} if api_key else {}),
                "anthropic-version": "2023-06-01",
            },
            {
                "model": connection.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
            },
        )
    escaped_model = urllib.parse.quote(connection.model_id, safe="")
    return (
        f"{endpoint}/models/{escaped_model}:generateContent",
        ({"x-goog-api-key": api_key} if api_key else {}),
        {"contents": [{"parts": [{"text": prompt}]}]},
    )


def _response_for(
    protocol: ModelProtocol, payload: Mapping[str, Any]
) -> tuple[str, ModelUsage]:
    try:
        if protocol is ModelProtocol.OPENAI_COMPATIBLE:
            text = str(payload["choices"][0]["message"]["content"])
            raw_usage = payload.get("usage", {})
            usage = ModelUsage(
                input_tokens=raw_usage.get("prompt_tokens"),
                output_tokens=raw_usage.get("completion_tokens"),
                total_tokens=raw_usage.get("total_tokens"),
            )
        elif protocol is ModelProtocol.ANTHROPIC:
            text = str(payload["content"][0]["text"])
            raw_usage = payload.get("usage", {})
            input_tokens = raw_usage.get("input_tokens")
            output_tokens = raw_usage.get("output_tokens")
            usage = ModelUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=(input_tokens + output_tokens)
                if isinstance(input_tokens, int) and isinstance(output_tokens, int)
                else None,
            )
        else:
            text = str(payload["candidates"][0]["content"]["parts"][0]["text"])
            raw_usage = payload.get("usageMetadata", {})
            usage = ModelUsage(
                input_tokens=raw_usage.get("promptTokenCount"),
                output_tokens=raw_usage.get("candidatesTokenCount"),
                total_tokens=raw_usage.get("totalTokenCount"),
            )
    except (KeyError, IndexError, TypeError) as error:
        raise ModelGatewayError(
            "model endpoint returned an unexpected schema"
        ) from error
    return text, usage


def _connection_from_row(row: Any) -> ModelConnection:
    return ModelConnection(
        connection_id=row["connection_id"],
        provider=row["provider"],
        protocol=row["protocol"],
        endpoint=row["endpoint"],
        model_id=row["model_id"],
        status=row["status"],
        last_error=row["last_error"],
        last_tested_at=datetime.fromisoformat(row["last_tested_at"])
        if row["last_tested_at"]
        else None,
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        credential_ref=row["credential_ref"],
        auth_mode=row["auth_mode"],
    )
