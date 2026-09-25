"""Bounded public discovery and original-page reads for the research Agent."""

from __future__ import annotations

import hashlib
import html
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from io import BytesIO

from pypdf import PdfReader

from jobfindsme.connectors.http import SafeRedirectHandler, validate_public_http_url

from .service import (
    _ReadableHtml,
    _excerpt_around,
    _host_matches,
    _normalized,
    _page_published_at,
    _published_at,
)

SITES = {
    "cninfo": ("cninfo.com.cn", "巨潮资讯", "official_disclosure"),
    "sse": ("sse.com.cn", "上海证券交易所", "official_disclosure"),
    "szse": ("szse.cn", "深圳证券交易所", "official_disclosure"),
    "hkex": ("hkexnews.hk", "港交所披露易", "official_disclosure"),
    "maimai": ("maimai.cn", "脉脉", "personal_account"),
    "kanzhun": ("kanzhun.com", "看准", "personal_account"),
    "zhihu": ("zhihu.com", "知乎", "personal_account"),
    "offershow": ("offershow.cn", "OfferShow", "personal_account"),
    "web": ("", "公开网页", "public_web"),
}


def _source_url(value: str, site: str) -> str:
    if site not in SITES:
        raise ValueError("unsupported research source")
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != "https" or parsed.port not in (None, 443)
            or parsed.username or parsed.password or not parsed.hostname
            or (site != "web" and not _host_matches(parsed.hostname, SITES[site][0]))):
        raise ValueError("research URL is outside the selected source")
    validate_public_http_url(value, resolve_dns=True, require_https=True)
    return value


def discover_sources(company: str, question: str, site: str, *, timeout: float = 4) -> list[dict]:
    if site not in SITES or not company.strip() or len(company) > 100 or not question.strip() or len(question) > 700:
        raise ValueError("invalid research discovery")
    domain, label, source_type = SITES[site]
    query = urllib.parse.urlencode(
        {"q": f'"{company.strip()}" {question.strip()}' + (f" site:{domain}" if domain else ""), "format": "rss"}
    )
    request = urllib.request.Request(
        f"https://www.bing.com/search?{query}",
        headers={"User-Agent": "JobFindsMe/desktop-research"},
    )
    validate_public_http_url("https://www.bing.com", resolve_dns=True, require_https=True)
    opener = urllib.request.build_opener(
        SafeRedirectHandler(max_redirects=2, require_https=True, same_host_only=True)
    )
    with opener.open(request, timeout=max(0.1, min(timeout, 4))) as response:
        body = response.read(1_000_000)
    root = ET.fromstring(body)
    hits = []
    seen = set()
    for item in root.findall(".//item")[:12]:
        url = (item.findtext("link") or "").strip()
        try:
            _source_url(url, site)
        except (ValueError, OSError):
            continue
        if url in seen:
            continue
        seen.add(url)
        summary = html.unescape(re.sub(r"<[^>]+>", " ", item.findtext("description") or ""))
        hits.append(
            {
                "url": url,
                "title": (item.findtext("title") or "").strip()[:300],
                "summary_hint": " ".join(summary.split())[:500],
                "search_published_at": _published_at(item.findtext("pubDate")),
                "site": site,
                "platform": label,
                "source_type": source_type,
                "status": "search_hint_only",
            }
        )
        if len(hits) >= 6:
            break
    return hits


def read_original_page(
    url: str,
    company: str,
    site: str,
    *,
    timeout: float = 4,
    opener=None,
) -> dict:
    """Only bounded same-host HTTPS HTML or text-layer PDF becomes evidence."""
    _source_url(url, site)
    if not company.strip() or len(company) > 100:
        raise ValueError("company is required")
    domain, label, source_type = SITES[site]
    opener = opener or urllib.request.build_opener(
        SafeRedirectHandler(max_redirects=2, require_https=True, same_host_only=True)
    )
    request = urllib.request.Request(url, headers={"User-Agent": "JobFindsMe/desktop-research"})
    retrieved_at = datetime.now(UTC).isoformat()
    try:
        with opener.open(request, timeout=max(0.1, min(timeout, 4))) as response:
            final_url = response.geturl()
            _source_url(final_url, site)
            content_type = response.headers.get_content_type()
            pdf_hint = content_type in {"application/pdf", "application/x-pdf"} or (content_type == "application/octet-stream" and urllib.parse.urlsplit(final_url).path.lower().endswith(".pdf"))
            if content_type not in {"text/html", "application/xhtml+xml"} and not pdf_hint:
                return {"url": final_url, "site": site, "status": "unsupported_source", "limit": "source is not HTML or PDF"}
            charset = response.headers.get_content_charset() or "utf-8"
            limit = 2_000_000 if pdf_hint else 1_000_000
            body = response.read(limit + 1)
            if len(body) > limit:
                return {"url": final_url, "site": site, "status": "unsupported_source", "limit": "source response too large"}
            if pdf_hint and not body.startswith(b"%PDF-"):
                return {"url": final_url, "site": site, "status": "unsupported_source", "limit": "PDF signature missing"}
    except urllib.error.HTTPError as error:
        status = "expired" if error.code in (404, 410) else "rate_limited" if error.code == 429 else "restricted"
        return {"url": url, "site": site, "status": status, "limit": f"HTTP {error.code}"}
    except (OSError, TimeoutError):
        return {"url": url, "site": site, "status": "read_failed", "limit": "original page unavailable"}
    page_number = None
    title = ""
    if pdf_hint:
        try:
            reader = PdfReader(BytesIO(body), strict=True)
            if reader.is_encrypted or len(reader.pages) > 40:
                return {"url": final_url, "site": site, "status": "unsupported_source", "limit": "encrypted or over 40 pages"}
            has_text_layer = False
            for index, page in enumerate(reader.pages):
                candidate = " ".join((page.extract_text() or "").split())[:12000]
                has_text_layer = has_text_layer or bool(candidate)
                if _normalized(company) in _normalized(candidate):
                    text, page_number = candidate, index + 1
                    break
            else:
                return {"url": final_url, "site": site, "status": "entity_mismatch" if has_text_layer else "no_text_layer", "limit": "company not found in PDF text" if has_text_layer else "PDF has no readable text layer"}
        except Exception:
            return {"url": final_url, "site": site, "status": "read_failed", "limit": "PDF text extraction failed"}
        anchored = True
    else:
        parser = _ReadableHtml()
        parser.feed(body.decode(charset, errors="replace"))
        text = " ".join((parser.article_text or parser.text).split())
        title = parser.title[:300]
        anchored = bool(parser.article_text) or _normalized(company) in _normalized(title)
    if len(text) < 50 or not anchored or _normalized(company) not in _normalized(text):
        return {"url": final_url, "site": site, "status": "entity_mismatch", "limit": "company not anchored in title or article body"}
    excerpt = _excerpt_around(text, company, limit=1200)
    published_at = _page_published_at(parser.meta) if not pdf_hint else None
    evidence_id = "ev_" + hashlib.sha256(f"{final_url}\0{excerpt}".encode()).hexdigest()[:24]
    return {
        "evidence_id": evidence_id,
        "url": final_url,
        "platform": label,
        "published_at": published_at,
        "retrieved_at": retrieved_at,
        "company": company,
        "team": None,
        "excerpt": excerpt,
        "evidence_kind": "public_source",
        "verification_status": "independently_retrieved",
        "relevance": "company",
        "limitations": "原文已读取；主体仅按页面名称匹配，集团、子公司和团队范围仍需核对。"
        + (" 页面未提供可核验发布日期。" if not published_at else ""),
        "context": {
            "source_type": source_type,
            "content_type": "application/pdf" if pdf_hint else content_type,
            "page": page_number,
            "company_match": "name_in_article",
            "entity_scope": "brand_or_legal_entity_unresolved",
            "link_status": "reachable",
            "research_topic": "company",
            "role": None,
            "region": None,
            "original_title": title,
        },
        "status": "read_original",
    }
