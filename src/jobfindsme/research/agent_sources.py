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
import zlib
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
    _host_matches,
    _normalized,
    _page_published_at,
    _published_at,
    _ReadableHtml,
)


def _question_terms(question: str, company: str) -> tuple[str, ...]:
    focus = question.casefold().replace(company.casefold(), " ")
    words = re.findall(r"[a-z0-9][a-z0-9.+#-]{1,30}|[\u3400-\u9fff]{2,}", focus)
    stop = {
        "怎么",
        "怎么样",
        "如何",
        "什么",
        "情况",
        "了解",
        "一下",
        "公司",
        "这个",
        "这家",
        "是否",
        "有没有",
        "请问",
    }
    terms: list[str] = []
    for word in words:
        if re.fullmatch(r"[\u3400-\u9fff]+", word):
            parts = re.split(r"(?:的|和|与|及|在|是|了|么|吗|请|帮我|看看)", word)
            for part in parts:
                if 2 <= len(part) <= 8 and part not in stop:
                    terms.append(part)
                elif len(part) > 8:
                    terms.extend(
                        part[index : index + 2] for index in range(len(part) - 1)
                    )
        elif word not in stop:
            terms.append(word)
    return tuple(dict.fromkeys(terms))[:12]


def _relevant_passage(
    text: str, question: str, company: str, limit: int = 1200
) -> tuple[str, int]:
    terms = _question_terms(question, company)
    if not terms:
        index = text.casefold().find(company.casefold())
        start = max(0, index - limit // 3) if index >= 0 else 0
        return text[start : start + limit], start
    lowered = text.casefold()
    positions = {0}
    for term in terms:
        cursor = 0
        for _ in range(100):
            index = lowered.find(term, cursor)
            if index < 0:
                break
            positions.add(max(0, index - limit // 3))
            cursor = index + len(term)
    best = max(
        positions,
        key=lambda start: (
            sum(
                (4 if len(term) >= 4 else 2)
                * lowered[start : start + limit].count(term)
                for term in terms
            ),
            -start,
        ),
    )
    return text[best : best + limit], best


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
    "github": ("github.com", "GitHub", "public_web"),
    "papers": ("", "论文来源", "public_web"),
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
        # Discovery stays direct; original pages follow the user's existing
        # network proxy. TLS and public-URL checks remain mandatory on both paths.
        urllib.request.ProxyHandler({} if search else None),
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
        or (SITES[site][0] and not _host_matches(parsed.hostname, SITES[site][0]))
        or (
            site == "papers"
            and not any(
                _host_matches(parsed.hostname, host)
                for host in ("arxiv.org", "doi.org", "aclanthology.org")
            )
        )
    ):
        raise ValueError("research URL is outside the selected source")
    validate_public_http_url(value, resolve_dns=True, require_https=True)
    return value


_BENEFIT_TERMS = re.compile(
    r"待遇|薪资|薪酬|福利|年终|加班|工作强度|工资|salary|benefit|compensation", re.I
)


def _topic_relevant(row: dict, question: str) -> bool:
    # Discovery relevance only: snippets never become evidence.
    hint = row.get("title", "") + " " + row.get("summary_hint", "")
    if re.search(r"行业|市场规模|产业|技术趋势|生态", question):
        parsed = urllib.parse.urlsplit(row.get("url", ""))
        if not parsed.path.strip("/") or re.search(
            r"/(?:xian-city|web/geek|jobs|sou)/", parsed.path
        ):
            return False
        return bool(
            re.search(
                r"报告|市场规模|市场研究|产业|行业分析|行业研究|发展趋势|商业模式|人力资源服务业"
                r"|report|industry|market|AI Index|outlook|trend",
                hint,
                re.I,
            )
        )
    if not _BENEFIT_TERMS.search(question):
        return True
    return bool(
        _BENEFIT_TERMS.search(row.get("title", "") + " " + row.get("summary_hint", ""))
    )


def _company_relevant(row: dict, company: str) -> bool:
    # Search snippets are only candidate hints. A short company name must be
    # visible in the hint before spending an original-page read on it.
    hint = row.get("title", "") + " " + row.get("summary_hint", "")
    return company.strip().casefold() in hint.casefold()


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
    query = (f'"{company}" {question}' if company else question) + (
        f" site:{domain}" if domain else ""
    )
    endpoint = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
        {"q": query}
    )
    validate_public_http_url(endpoint, resolve_dns=True, require_https=True)
    request = urllib.request.Request(
        endpoint, headers={"User-Agent": "JobFindsMe/desktop-research"}
    )
    # An unavailable public search page must not consume the entire research run.
    with _research_opener(search=False).open(
        request, timeout=min(3, remaining)
    ) as response:
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
        if (
            target in seen
            or not _company_relevant(row, company)
            or not _topic_relevant(row, question)
        ):
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
        or len(company) > 100
        or not question.strip()
        or len(question) > 700
    ):
        raise ValueError("invalid research discovery")
    if not company and site == "web":
        from .web_providers import exa_search

        optional = exa_search(
            question,
            opener=_research_opener(search=False),
            timeout=max(0.1, min(timeout, 10)),
        )
        if optional is not None:
            return optional
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
    validate_public_http_url(
        "https://www.bing.com", resolve_dns=True, require_https=True
    )
    opener = _research_opener(search=True)
    network_retry_used = False

    def rss_hits(search_text: str) -> list[dict]:
        nonlocal network_retry_used
        query = urllib.parse.urlencode(
            {"q": search_text + (f" site:{domain}" if domain else ""), "format": "rss"}
        )
        request = urllib.request.Request(
            f"https://www.bing.com/search?{query}",
            headers={"User-Agent": "JobFindsMe/desktop-research"},
        )
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("research discovery time budget exhausted")
            try:
                with opener.open(
                    request, timeout=max(0.1, min(4, remaining))
                ) as response:
                    body = response.read(1_000_000)
                break
            except urllib.error.HTTPError:
                raise
            except (urllib.error.URLError, TimeoutError):
                if network_retry_used or deadline - time.monotonic() <= 0.1:
                    raise
                network_retry_used = True
        root = ET.fromstring(body)
        hits, seen = [], set()
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
        return hits

    hits = rss_hits(
        f'"{company.strip()}" {question.strip()}' if company else question.strip()
    )
    if company and hits and not any(_company_relevant(row, company) for row in hits):
        # A noisy broad query gets one shorter request to the same provider.
        # Any HTTP or verification error propagates; there is no bypass.
        hits = rss_hits(f'"{company.strip()}"')
        return [
            row
            for row in hits
            if _company_relevant(row, company)
            and _topic_relevant(row, original_question or question)
        ]
    relevant = [
        row
        for row in hits
        if _company_relevant(row, company)
        and _topic_relevant(row, original_question or question)
    ]
    if relevant:
        return relevant
    return _fallback_discovery(company.strip(), question.strip(), site, deadline)


def read_original_page(
    url: str,
    company: str,
    site: str,
    *,
    question: str = "",
    timeout: float = 4,
    opener=None,
) -> dict:
    """Only bounded same-host HTTPS HTML or text-layer PDF becomes evidence."""
    _source_url(url, site)
    if len(company) > 100:
        raise ValueError("subject is too long")
    domain, label, source_type = SITES[site]
    if site == "web" and is_tencent_disclosure_url(url, company):
        label, source_type = "腾讯投资者关系", "official_disclosure"
    opener = opener or _research_opener(search=False)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "JobFindsMe/desktop-research",
            "Accept-Encoding": "identity",
        },
    )
    retrieved_at = datetime.now(UTC).isoformat()
    try:
        with opener.open(request, timeout=max(0.1, min(timeout, 8))) as response:
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
            content_encoding = (
                getattr(response.headers, "get", lambda *_: "")("Content-Encoding", "")
                .strip()
                .lower()
            )
            if content_encoding in {"gzip", "x-gzip"} or (
                not content_encoding and body.startswith(b"\x1f\x8b")
            ):
                decoder = zlib.decompressobj(zlib.MAX_WBITS | 16)
            elif content_encoding == "deflate":
                decoder = zlib.decompressobj()
            elif content_encoding in {"", "identity"}:
                decoder = None
            else:
                return {
                    "url": final_url,
                    "site": site,
                    "status": "unsupported_source",
                    "limit": "unsupported content encoding",
                }
            if decoder is not None:
                try:
                    expanded = decoder.decompress(body, limit + 1)
                except zlib.error:
                    expanded = b""
                if not decoder.eof or decoder.unconsumed_tail or len(expanded) > limit:
                    return {
                        "url": final_url,
                        "site": site,
                        "status": "unsupported_source",
                        "limit": "compressed source is invalid or too large",
                    }
                body = expanded
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
            if error.code in (401, 403)
            else "read_failed"
        )
        return {
            "url": url,
            "site": site,
            "status": status,
            "limit": f"HTTP {error.code}",
        }
    except urllib.error.URLError as error:
        return {
            "url": url,
            "site": site,
            "status": "read_failed",
            "limit": "TLS certificate failure"
            if isinstance(error.reason, ssl.SSLError)
            else "original page unavailable",
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
    passage_start = 0
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
            candidates: list[tuple[int, str, str, int]] = []
            subject_found = False
            for index, page in enumerate(reader.pages):
                candidate = " ".join((page.extract_text() or "").split())[:12000]
                has_text_layer = has_text_layer or bool(candidate)
                subject_found = subject_found or _normalized(company) in _normalized(
                    candidate
                )
                if candidate:
                    passage, start = _relevant_passage(candidate, question, company)
                    candidates.append((index + 1, candidate, passage, start))
            if not subject_found:
                return {
                    "url": final_url,
                    "site": site,
                    "status": "entity_mismatch" if has_text_layer else "no_text_layer",
                    "limit": "company not found in PDF text"
                    if has_text_layer
                    else "PDF has no readable text layer",
                }
            terms = _question_terms(question, company)
            page_number, text, _passage, passage_start = max(
                candidates,
                key=lambda item: (
                    sum(item[2].casefold().count(term) for term in terms),
                    int(_normalized(company) in _normalized(item[1])),
                    -item[0],
                ),
            )
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
        decoded = body.decode(charset, errors="replace")
        if decoded.count("\ufffd") > max(3, len(decoded) // 100):
            return {
                "url": final_url,
                "site": site,
                "status": "unsupported_source",
                "limit": "source text is not readable",
            }
        parser.feed(decoded)
        text = " ".join((parser.article_text or parser.text).split())
        title = parser.title[:300]
        anchored = (
            not company
            or bool(parser.article_text)
            or _normalized(company) in _normalized(title)
        )
    if (
        len(text) < 50
        or not anchored
        or (company and not pdf_hint and _normalized(company) not in _normalized(text))
    ):
        return {
            "url": final_url,
            "site": site,
            "status": "entity_mismatch",
            "limit": "company not anchored in title or article body",
        }
    excerpt, passage_start = _relevant_passage(text, question, company)
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
        "relevance": "company" if company else "web",
        "limitations": ("原文已读取；主体与时间范围需核对。")
        + (" 页面未提供可核验发布日期。" if not published_at else ""),
        "context": {
            "source_type": source_type,
            "content_type": "application/pdf" if pdf_hint else content_type,
            "page": page_number,
            "start_char": passage_start,
            "end_char": passage_start + len(excerpt),
            "passage_id": hashlib.sha256(
                f"{final_url}\0{page_number}\0{passage_start}".encode()
            ).hexdigest()[:20],
            "source_id": hashlib.sha256(final_url.encode()).hexdigest()[:20],
            "company_match": ("name_in_document" if pdf_hint else "name_in_article")
            if company
            else "not_requested",
            "entity_scope": "brand_or_legal_entity_unresolved",
            "link_status": "reachable",
            "research_topic": "company" if company else "web",
            "retrieval_method": "http",
            "role": None,
            "region": None,
            "original_title": title,
        },
        "status": "read_original",
    }
