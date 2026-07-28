from __future__ import annotations

from urllib.request import Request

import pytest

from jobfindsme.connectors import ConnectorPolicy
from jobfindsme.connectors.http import (
    SafeRedirectHandler,
    UnsafeSourceError,
    validate_public_http_url,
)


def test_connector_refuses_unapproved_source_policy() -> None:
    policy = ConnectorPolicy(public_access=True, robots_allowed=False)
    assert not policy.can_fetch


def test_authorized_policy_overrides_robots_block() -> None:
    policy = ConnectorPolicy(
        public_access=True, robots_allowed=False, authorized=True
    )
    assert policy.can_fetch


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost/jobs",
        "http://127.0.0.1/jobs",
        "https://user:secret@example.com/jobs",
    ],
)
def test_url_validation_blocks_local_or_credentialed_sources(url: str) -> None:
    with pytest.raises(UnsafeSourceError):
        validate_public_http_url(url)


def test_redirect_target_is_validated_before_following() -> None:
    handler = SafeRedirectHandler(max_redirects=3, require_https=True)
    request = Request("https://public.example/jobs")

    with pytest.raises(UnsafeSourceError):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "http://127.0.0.1/private",
        )
