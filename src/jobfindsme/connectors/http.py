from __future__ import annotations

import gzip
import ipaddress
import socket
import ssl
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

import certifi


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
    timeout_seconds: float = 20
    max_bytes: int = 15_000_000
    max_decoded_bytes: int = 30_000_000
    max_redirects: int = 3
    attempts: int = 2
    retry_delay_seconds: float = 0.2
    require_https: bool = True
    same_host_redirects_only: bool = True

    def get(self, url: str) -> bytes:
        validate_public_http_url(
            url,
            resolve_dns=True,
            require_https=self.require_https,
        )
        last_error: OSError | None = None
        for attempt in range(self.attempts):
            try:
                return self._get_once(url)
            except (TimeoutError, OSError) as error:
                last_error = error
                if attempt + 1 < self.attempts:
                    time.sleep(self.retry_delay_seconds)
        assert last_error is not None
        raise last_error

    def _get_once(self, url: str) -> bytes:
        request = Request(
            url,
            headers={
                "User-Agent": "JobFindsMe/0.2",
                "Accept-Encoding": "gzip",
            },
        )
        tls_context = ssl.create_default_context(cafile=certifi.where())
        opener = build_opener(
            SafeRedirectHandler(
                max_redirects=self.max_redirects,
                require_https=self.require_https,
                same_host_only=self.same_host_redirects_only,
            ),
            HTTPSHandler(context=tls_context),
        )
        with opener.open(request, timeout=self.timeout_seconds) as response:
            final_url = response.geturl()
            validate_public_http_url(
                final_url,
                resolve_dns=True,
                require_https=self.require_https,
            )
            data = response.read(self.max_bytes + 1)
            encoding = response.headers.get("Content-Encoding", "").casefold()
        if len(data) > self.max_bytes:
            raise ValueError("source response exceeds configured size limit")
        if encoding == "gzip":
            data = gzip.decompress(data)
        if len(data) > self.max_decoded_bytes:
            raise ValueError("decoded source response exceeds configured size limit")
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
