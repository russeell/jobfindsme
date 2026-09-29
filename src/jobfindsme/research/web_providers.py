"""Optional discovery/reader adapters, disabled until explicitly configured.

No model, browser, recruitment session or Agent Reach runtime is used here.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime

from jobfindsme.connectors.http import validate_public_http_url


def provider_status():
    return {
        "public_search": {"configured": True, "status": "not_probed"},
        "exa": {
            "configured": bool(os.environ.get("JOBFINDSME_EXA_API_KEY")),
            "status": "not_probed",
        },
        "jina_reader": {
            "configured": os.environ.get("JOBFINDSME_JINA_READER") == "1",
            "status": "not_probed",
        },
    }


def exa_search(query: str, *, opener, timeout: float) -> list[dict] | None:
    key = os.environ.get("JOBFINDSME_EXA_API_KEY")
    if not key:
        return None
    request = urllib.request.Request(
        "https://api.exa.ai/search",
        data=json.dumps(
            {
                "query": query,
                "numResults": 6,
                "type": "auto",
                "contents": {"text": False},
            }
        ).encode(),
        headers={"Content-Type": "application/json", "x-api-key": key},
        method="POST",
    )
    with opener.open(request, timeout=timeout) as response:
        body = response.read(1_000_001)
    if len(body) > 1_000_000:
        raise ValueError("search response too large")
    data = json.loads(body)
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ValueError("invalid search response")
    rows = []
    for row in data["results"][:6]:
        if not isinstance(row, dict):
            continue
        url = row.get("url", "")
        try:
            validate_public_http_url(url, resolve_dns=True, require_https=True)
        except (ValueError, OSError):
            continue
        rows.append(
            {
                "url": url,
                "title": str(row.get("title") or "")[:300],
                "site": "web",
                "platform": "公开网页",
                "provider": "exa",
                "source_type": "public_web",
                "status": "search_hint_only",
                "search_published_at": row.get("publishedDate"),
            }
        )
    return rows


def jina_read(url: str, *, opener, timeout: float) -> dict | None:
    if os.environ.get("JOBFINDSME_JINA_READER") != "1":
        return None
    validate_public_http_url(url, resolve_dns=True, require_https=True)
    request = urllib.request.Request(
        "https://r.jina.ai/" + url,
        headers={
            "Accept": "text/plain",
            "X-No-Cache": "false",
            "X-Return-Format": "text",
            "User-Agent": "JobFindsMe/desktop-research",
        },
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(1_000_001)
    except urllib.error.HTTPError as error:
        return {
            "url": url,
            "site": "web",
            "status": "rate_limited"
            if error.code == 429
            else "restricted"
            if error.code in (401, 403)
            else "read_failed",
            "limit": f"HTTP {error.code}",
        }
    except (OSError, TimeoutError):
        return {
            "url": url,
            "site": "web",
            "status": "read_failed",
            "limit": "reader unavailable",
        }
    if len(body) > 1_000_000:
        return {
            "url": url,
            "site": "web",
            "status": "unsupported_source",
            "limit": "reader response too large",
        }
    text = body.decode("utf-8", errors="replace")
    # Reader output must identify the exact URL; error/metadata pages are not originals.
    if ("URL Source: " + url) not in {
        line.strip() for line in text.splitlines()
    } or "Markdown Content:" not in text:
        return {
            "url": url,
            "site": "web",
            "status": "read_failed",
            "limit": "reader origin not confirmed",
        }
    excerpt = text.split("Markdown Content:", 1)[1].strip()[:1200]
    if len(excerpt) < 50:
        return {
            "url": url,
            "site": "web",
            "status": "read_failed",
            "limit": "reader text too short",
        }
    return {
        "url": url,
        "site": "web",
        "status": "read_original",
        "evidence_id": "ev_"
        + hashlib.sha256((url + "\0" + excerpt).encode()).hexdigest()[:24],
        "excerpt": excerpt,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "published_at": None,
        "platform": "公开网页（Jina Reader）",
        "company": "",
        "team": None,
        "evidence_kind": "public_source",
        "verification_status": "independently_retrieved",
        "relevance": "web",
        "limitations": (
            "外部Reader取得的正文；来源原URL已确认，发布日期与完整范围仍需核对。"
        ),
        "context": {
            "source_type": "public_web",
            "research_topic": "web",
            "retrieval_method": "jina_reader",
            "link_status": "reader_retrieved",
        },
    }
