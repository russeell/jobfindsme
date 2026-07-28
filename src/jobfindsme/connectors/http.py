from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class UnsafeSourceError(ValueError):
    pass


class HttpTransport(Protocol):
    def get(self, url: str) -> bytes: ...


def validate_public_http_url(url: str, *, resolve_dns: bool = False) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeSourceError("source URL must use public HTTP(S)")
    if parsed.username or parsed.password:
        raise UnsafeSourceError("source URL cannot contain credentials")
    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith(".local"):
        raise UnsafeSourceError("local source URLs are not allowed")

    addresses: list[str] = []
    try:
        addresses.append(str(ipaddress.ip_address(hostname)))
    except ValueError:
        if resolve_dns:
            addresses.extend(
                info[4][0] for info in socket.getaddrinfo(hostname, parsed.port or 443)
            )
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise UnsafeSourceError("private or reserved source URLs are not allowed")


@dataclass(frozen=True)
class UrllibTransport:
    timeout_seconds: float = 10
    max_bytes: int = 5_000_000

    def get(self, url: str) -> bytes:
        validate_public_http_url(url, resolve_dns=True)
        request = Request(url, headers={"User-Agent": "JobFindsMe/0.1"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            final_url = response.geturl()
            validate_public_http_url(final_url, resolve_dns=True)
            data = response.read(self.max_bytes + 1)
        if len(data) > self.max_bytes:
            raise ValueError("source response exceeds configured size limit")
        return data
