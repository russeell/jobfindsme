from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from jobfindsme.monitoring import MonitorSummary


class JsonTransport(Protocol):
    def post(self, url: str, payload: dict[str, object]) -> dict[str, object]: ...


@dataclass(frozen=True)
class UrllibJsonTransport:
    timeout_seconds: float = 10

    def post(self, url: str, payload: dict[str, object]) -> dict[str, object]:
        request = Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read(1_000_000))


def feishu_signature(timestamp: int, secret: str) -> str:
    key = f"{timestamp}\n{secret}".encode()
    digest = hmac.new(key, digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


class FeishuNotifier:
    def __init__(
        self,
        *,
        webhook_url: str,
        secret: str,
        transport: JsonTransport | None = None,
        clock: Callable[[], int] = lambda: int(time.time()),
        max_jobs: int = 10,
        max_chars: int = 3000,
    ) -> None:
        parsed = urlparse(webhook_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"open.feishu.cn", "open.larksuite.com"}
            or "/open-apis/bot/" not in parsed.path
        ):
            raise ValueError("invalid Feishu/Lark webhook URL")
        if not secret:
            raise ValueError("Feishu signing secret is required")
        self.webhook_url = webhook_url
        self.secret = secret
        self.transport = transport or UrllibJsonTransport()
        self.clock = clock
        self.max_jobs = max_jobs
        self.max_chars = max_chars

    @classmethod
    def from_env(cls) -> FeishuNotifier | None:
        webhook = os.getenv("FEISHU_WEBHOOK_URL")
        secret = os.getenv("FEISHU_SECRET")
        if not webhook and not secret:
            return None
        if not webhook or not secret:
            raise ValueError("both FEISHU_WEBHOOK_URL and FEISHU_SECRET are required")
        return cls(webhook_url=webhook, secret=secret)

    def send(self, summary: MonitorSummary) -> None:
        timestamp = self.clock()
        text = self._render(summary)[: self.max_chars]
        payload = {
            "timestamp": str(timestamp),
            "sign": feishu_signature(timestamp, self.secret),
            "msg_type": "text",
            "content": {"text": text},
        }
        result = self.transport.post(self.webhook_url, payload)
        if result.get("code", 0) != 0:
            raise RuntimeError(str(result.get("msg", "Feishu notification failed")))

    def _render(self, summary: MonitorSummary) -> str:
        lines = [
            f"jobfindsme：发现 {len(summary.new_matches)} 个新匹配岗位",
        ]
        for match in summary.new_matches[: self.max_jobs]:
            lines.append(
                f"- {match.job.title}｜{match.job.company}｜"
                f"{', '.join(match.job.locations) or '地点未知'}｜"
                f"{match.job.apply_url}"
            )
        if len(summary.new_matches) > self.max_jobs:
            lines.append(
                f"另有 {len(summary.new_matches) - self.max_jobs} 个岗位未展开"
            )
        return "\n".join(lines)
