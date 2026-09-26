"""Bounded public discovery and original-page reads for the research Agent."""

from __future__ import annotations

import hashlib
import html
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from html.parser import HTMLParser
from io import BytesIO

import certifi
from pypdf import PdfReader

from jobfindsme.connectors.http import (
    SafeRedirectHandler,
    UnsafeSourceError,
    validate_public_http_url,
)

from .service import (
    _excerpt_around,
    _host_matches,
    _normalized,
    _page_published_at,
    _published_at,
    _ReadableHtml,
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

_TENCENT_RESULTS = "https://www.tencent.com/zh-cn/investors/results/"
_TENCENT_HOSTS = frozenset({"www.tencent.com", "static.www.tencent.com"})


def is_tencent_disclosure_url(url: str, company: str) -> bool:
    if company.strip() not in {"腾讯", "腾讯控股", "腾讯控股有限公司"}:
        return False
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _TENCENT_HOSTS
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
    ):
        return False
    return parsed.path == "/zh-cn/investors/results/" or (
        parsed.path.lower().endswith(".pdf")
        and (
            parsed.path.startswith("/uploads/")
            or parsed.path.startswith("/wp-content/uploads/")
        )
    )


class _TencentResultsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.heading = ""
        self._in_heading = False
        self._link = ""
        self._link_text = ""
        self.results: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "h3" or (
            tag == "h2" and "text-white" in dict(attrs).get("class", "").split()
        ):
            self._in_heading = True
            self.heading = ""
        elif tag == "a":
            self._link = dict(attrs).get("href", "")
            self._link_text = ""

    def handle_data(self, data):
        if self._in_heading:
            self.heading += data
        if self._link:
            self._link_text += data

    def handle_endtag(self, tag):
        if tag in {"h2", "h3"}:
            self._in_heading = False
        elif tag == "a":
            if "业绩新闻" in self._link_text and "业绩" in self.heading:
                self.results.append((self._link, self.heading.strip()))
            self._link = ""


def _tencent_disclosures(company: str, question: str, timeout: float) -> list[dict]:
    if company.strip() not in {"腾讯", "腾讯控股", "腾讯控股有限公司"}:
        return []
    _source_url(_TENCENT_RESULTS, "web")
    request = urllib.request.Request(
        _TENCENT_RESULTS, headers={"User-Agent": "JobFindsMe/desktop-research"}
    )
    with _research_opener(search=False).open(
        request, timeout=max(0.1, min(timeout, 4))
    ) as response:
        if (
            response.geturl() != _TENCENT_RESULTS
            or response.headers.get_content_type() != "text/html"
        ):
            return []
        body = response.read(250_001)
    if len(body) > 250_000:
        return []
    parser = _TencentResultsParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    year = re.search(r"20\d{2}", question)
    year_chinese = (
        ""
        if not year
        else "二零" + "".join("零一二三四五六七八九"[int(d)] for d in year.group()[2:])
    )
    hits = []
    for url, heading in parser.results[:100]:
        host = urllib.parse.urlsplit(url).hostname
        if host not in _TENCENT_HOSTS or not urllib.parse.urlsplit(
            url
        ).path.lower().endswith(".pdf"):
            continue
        if year and year.group() not in heading and year_chinese not in heading:
            continue
        try:
            _source_url(url, "web")
        except (ValueError, OSError):
            continue
        hits.append(
            {
                "url": url,
                "title": heading[:300],
                "summary_hint": "腾讯官方投资者关系业绩新闻原文",
                "search_published_at": None,
                "site": "web",
                "platform": "腾讯投资者关系",
                "source_type": "official_disclosure",
                "provider": "official_index",
                "status": "search_hint_only",
            }
        )
        if len(hits) >= 3:
            break
    return hits


class BingRedirectHandler(SafeRedirectHandler):
    """Permit Bing's regional RSS redirect without opening arbitrary hosts."""

    _HOSTS = frozenset({"www.bing.com", "cn.bing.com"})

    def __init__(self, *, max_redirects: int, require_https: bool) -> None:
        super().__init__(
            max_redirects=max_redirects,
            require_https=require_https,
            same_host_only=False,
        )

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        original_host = urllib.parse.urlsplit(req.full_url).hostname
        next_host = urllib.parse.urlsplit(newurl).hostname
        if original_host not in self._HOSTS or next_host not in self._HOSTS:
            raise UnsafeSourceError("search provider redirect left Bing")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _research_opener(*, search: bool):
    redirect = (
        BingRedirectHandler(max_redirects=2, require_https=True)
        if search
        else SafeRedirectHandler(
            max_redirects=2, require_https=True, same_host_only=True
        )
    )
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(
            context=ssl.create_default_context(cafile=certifi.where())
        ),
        redirect,
    )


def _source_url(value: str, site: str) -> str:
    if site not in SITES:
        raise ValueError("unsupported research source")
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or not parsed.hostname
        or (site != "web" and not _host_matches(parsed.hostname, SITES[site][0]))
    ):
        raise ValueError("research URL is outside the selected source")
    validate_public_http_url(value, resolve_dns=True, require_https=True)
    return value


_BENEFIT_TERMS = re.compile(
    r"待遇|薪资|薪酬|福利|年终|加班|工作强度|工资|salary|benefit|compensation", re.I
)


def _topic_relevant(row: dict, question: str) -> bool:
    # Discovery relevance only: snippets never become evidence.
    if not _BENEFIT_TERMS.search(question):
        return True
    return bool(
        _BENEFIT_TERMS.search(row.get("title", "") + " " + row.get("summary_hint", ""))
    )


class _SearchHtml(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.anchor = False
        self.snippet = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "a" and "result__a" in classes:
            self.rows.append(
                {"url": attrs.get("href", ""), "title": "", "summary_hint": ""}
            )
            self.anchor = True
        if "result__snippet" in classes:
            self.snippet = True

    def handle_endtag(self, tag):
        if tag == "a":
            self.anchor = False
            self.snippet = False

    def handle_data(self, data):
        if self.rows and (self.anchor or self.snippet):
            key = "title" if self.anchor else "summary_hint"
            self.rows[-1][key] += data


def _fallback_discovery(
    company: str, question: str, site: str, deadline: float
) -> list[dict]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("research discovery time budget exhausted")
    domain, label, source_type = SITES[site]
    query = f'"{company}" {question}' + (f" site:{domain}" if domain else "")
    endpoint = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
        {"q": query}
    )
    validate_public_http_url(endpoint, resolve_dns=True, require_https=True)
    request = urllib.request.Request(
        endpoint, headers={"User-Agent": "JobFindsMe/desktop-research"}
    )
    with _research_opener(search=False).open(request, timeout=remaining) as response:
        body = response.read(1_000_000).decode("utf-8", errors="replace")
    if re.search(r"anomaly\.js|challenge-form|captcha", body, re.I):
        raise urllib.error.HTTPError(
            endpoint, 429, "search verification required", None, None
        )
    parser = _SearchHtml()
    parser.feed(body)
    rows, seen = [], set()
    for row in parser.rows[:20]:
        target = urllib.parse.urljoin("https://html.duckduckgo.com", row["url"])
        parsed = urllib.parse.urlsplit(target)
        if parsed.hostname in {"duckduckgo.com", "html.duckduckgo.com"}:
            target = urllib.parse.parse_qs(parsed.query).get("uddg", [target])[0]
        try:
            _source_url(target, site)
        except (ValueError, OSError):
            continue
        if target in seen or not _topic_relevant(row, question):
            continue
        seen.add(target)
        rows.append(
            {
                **row,
                "url": target,
                "site": site,
                "platform": label,
                "source_type": source_type,
                "provider": "duckduckgo_html",
                "status": "search_hint_only",
                "search_published_at": None,
            }
        )
        if len(rows) >= 6:
            break
    return rows


def discover_sources(
    company: str,
    question: str,
    site: str,
    *,
    timeout: float = 10,
    original_question: str | None = None,
) -> list[dict]:
    if (
        site not in SITES
        or not company.strip()
        or len(company) > 100
        or not question.strip()
        or len(question) > 700
    ):
        raise ValueError("invalid research discovery")
    deadline = time.monotonic() + max(0.1, min(timeout, 10))
    if site in {"hkex", "web"} and re.search(
        r"经营|业绩|财报|年报|披露|收入|利润|results|report|revenue", question, re.I
    ):
        try:
            official = _tencent_disclosures(
                company,
                original_question or question,
                max(0.1, deadline - time.monotonic()),
            )
        except urllib.error.HTTPError as error:
            if error.code in {403, 429}:
                raise
            official = []
        except (OSError, TimeoutError, ValueError, ET.ParseError):
            official = []
        if official:
            return official
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("research discovery time budget exhausted")
    domain, label, source_type = SITES[site]
    query = urllib.parse.urlencode(
        {
            "q": f'"{company.strip()}" {question.strip()}'
            + (f" site:{domain}" if domain else ""),
            "format": "rss",
        }
    )
    request = urllib.request.Request(
        f"https://www.bing.com/search?{query}",
        headers={"User-Agent": "JobFindsMe/desktop-research"},
    )
    validate_public_http_url(
        "https://www.bing.com", resolve_dns=True, require_https=True
    )
    opener = _research_opener(search=True)
    with opener.open(request, timeout=max(0.1, min(4, remaining))) as response:
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
        summary = html.unescape(
            re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
        )
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
    relevant = [
        row for row in hits if _topic_relevant(row, original_question or question)
    ]
    if relevant:
        return relevant
    return _fallback_discovery(company.strip(), question.strip(), site, deadline)


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
    if site == "web" and is_tencent_disclosure_url(url, company):
        label, source_type = "腾讯投资者关系", "official_disclosure"
    opener = opener or _research_opener(search=False)
    request = urllib.request.Request(
        url, headers={"User-Agent": "JobFindsMe/desktop-research"}
    )
    retrieved_at = datetime.now(UTC).isoformat()
    try:
        with opener.open(request, timeout=max(0.1, min(timeout, 4))) as response:
            final_url = response.geturl()
            _source_url(final_url, site)
            content_type = response.headers.get_content_type()
            pdf_hint = content_type in {"application/pdf", "application/x-pdf"} or (
                content_type == "application/octet-stream"
                and urllib.parse.urlsplit(final_url).path.lower().endswith(".pdf")
            )
            if (
                content_type not in {"text/html", "application/xhtml+xml"}
                and not pdf_hint
            ):
                return {
                    "url": final_url,
                    "site": site,
                    "status": "unsupported_source",
                    "limit": "source is not HTML or PDF",
                }
            charset = response.headers.get_content_charset() or "utf-8"
            limit = 2_000_000 if pdf_hint else 1_000_000
            body = response.read(limit + 1)
            if len(body) > limit:
                return {
                    "url": final_url,
                    "site": site,
                    "status": "unsupported_source",
                    "limit": "source response too large",
                }
            if pdf_hint and not body.startswith(b"%PDF-"):
                return {
                    "url": final_url,
                    "site": site,
                    "status": "unsupported_source",
                    "limit": "PDF signature missing",
                }
    except urllib.error.HTTPError as error:
        status = (
            "expired"
            if error.code in (404, 410)
            else "rate_limited"
            if error.code == 429
            else "restricted"
        )
        return {
            "url": url,
            "site": site,
            "status": status,
            "limit": f"HTTP {error.code}",
        }
    except (OSError, TimeoutError):
        return {
            "url": url,
            "site": site,
            "status": "read_failed",
            "limit": "original page unavailable",
        }
    page_number = None
    title = ""
    if pdf_hint:
        try:
            reader = PdfReader(BytesIO(body), strict=True)
            if reader.is_encrypted or len(reader.pages) > 40:
                return {
                    "url": final_url,
                    "site": site,
                    "status": "unsupported_source",
                    "limit": "encrypted or over 40 pages",
                }
            has_text_layer = False
            for index, page in enumerate(reader.pages):
                candidate = " ".join((page.extract_text() or "").split())[:12000]
                has_text_layer = has_text_layer or bool(candidate)
                if _normalized(company) in _normalized(candidate):
                    text, page_number = candidate, index + 1
                    break
            else:
                return {
                    "url": final_url,
                    "site": site,
                    "status": "entity_mismatch" if has_text_layer else "no_text_layer",
                    "limit": "company not found in PDF text"
                    if has_text_layer
                    else "PDF has no readable text layer",
                }
        except Exception:
            return {
                "url": final_url,
                "site": site,
                "status": "read_failed",
                "limit": "PDF text extraction failed",
            }
        anchored = True
    else:
        parser = _ReadableHtml()
        parser.feed(body.decode(charset, errors="replace"))
        text = " ".join((parser.article_text or parser.text).split())
        title = parser.title[:300]
        anchored = bool(parser.article_text) or _normalized(company) in _normalized(
            title
        )
    if len(text) < 50 or not anchored or _normalized(company) not in _normalized(text):
        return {
            "url": final_url,
            "site": site,
            "status": "entity_mismatch",
            "limit": "company not anchored in title or article body",
        }
    excerpt = _excerpt_around(text, company, limit=1200)
    published_at = _page_published_at(parser.meta) if not pdf_hint else None
    evidence_id = (
        "ev_" + hashlib.sha256(f"{final_url}\0{excerpt}".encode()).hexdigest()[:24]
    )
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
        "limitations": (
            "原文已读取；主体仅按页面名称匹配，集团、子公司和团队范围仍需核对。"
        )
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
