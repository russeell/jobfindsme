from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class UnsafeSourceError(ValueError):
    pass


class HttpTransport(Protocol):
    def get(self, url: str) -> bytes: ...


def validate_public_http_url(
    url: str,
    *,
    resolve_dns: bool = False,
    require_https: bool = False,
) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeSourceError("source URL must use public HTTP(S)")
    if require_https and parsed.scheme != "https":
        raise UnsafeSourceError("remote source URL must use HTTPS")
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
    max_redirects: int = 3
    require_https: bool = True
    same_host_redirects_only: bool = True

    def get(self, url: str) -> bytes:
        validate_public_http_url(
            url,
            resolve_dns=True,
            require_https=self.require_https,
        )
        request = Request(url, headers={"User-Agent": "JobFindsMe/0.1"})
        opener = build_opener(
            SafeRedirectHandler(
                max_redirects=self.max_redirects,
                require_https=self.require_https,
                same_host_only=self.same_host_redirects_only,
            )
        )
        with opener.open(request, timeout=self.timeout_seconds) as response:
            final_url = response.geturl()
            validate_public_http_url(
                final_url,
                resolve_dns=True,
                require_https=self.require_https,
            )
            data = response.read(self.max_bytes + 1)
        if len(data) > self.max_bytes:
            raise ValueError("source response exceeds configured size limit")
        return data


class SafeRedirectHandler(HTTPRedirectHandler):
    """Validate every redirect target before urllib opens the next connection."""

    def __init__(
        self,
        *,
        max_redirects: int,
        require_https: bool,
        same_host_only: bool = True,
    ) -> None:
        self.max_redirects = max_redirects
        self.require_https = require_https
        self.same_host_only = same_host_only
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_http_url(
            newurl,
            resolve_dns=True,
            require_https=self.require_https,
        )
        if (
            self.same_host_only
            and urlparse(req.full_url).hostname != urlparse(newurl).hostname
        ):
            raise UnsafeSourceError("cross-host source redirects are not allowed")
        redirect_count = getattr(req, "_jobfindsme_redirect_count", 0) + 1
        if redirect_count > self.max_redirects:
            raise UnsafeSourceError("source exceeded the redirect limit")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            redirected._jobfindsme_redirect_count = redirect_count
        return redirected
