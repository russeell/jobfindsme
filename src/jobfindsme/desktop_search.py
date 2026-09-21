from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from jobfindsme.connectors import ConnectorPolicy, RawJobRecord
from jobfindsme.desktop_sources import DesktopSourceService, SourceGateError
from jobfindsme.privacy import create_analysis_copy
from jobfindsme.profiles.service import ResumeProfileService

_TERM_SPLIT = re.compile(r"[\s,，、;；/|]+")
_TECH_TERM = re.compile(r"[A-Za-z][A-Za-z0-9.+#_-]{1,30}")
_PRIVATE_PLACEHOLDER = re.compile(r"\[已过滤:[^\]]+\]")


class SearchPreflightError(ValueError):
    pass


@dataclass(frozen=True)
class SearchPreflight:
    workspace_id: str
    resume_version_id: str | None
    keywords: tuple[str, ...]
    allowed_source_ids: tuple[str, ...]
    blocked_sources: dict[str, str]
    max_pages: int
    time_budget_seconds: float


@dataclass(frozen=True)
class SourcePage:
    records: tuple[RawJobRecord, ...]
    next_cursor: str | None = None


class PagedSourceAdapter(Protocol):
    def fetch_page(self, cursor: str | None) -> SourcePage: ...


@dataclass(frozen=True)
class SourceExecutionResult:
    records: tuple[RawJobRecord, ...]
    pages_fetched: int
    elapsed_seconds: float
    coverage_status: str
    can_continue: bool
    next_cursor: str | None
    stop_reason: str


class ExistingConnectorAdapter:
    """Expose an existing one-shot connector through the paged contract."""

    def __init__(self, connector) -> None:
        self.connector = connector

    def fetch_page(self, cursor: str | None) -> SourcePage:
        if cursor is not None:
            raise ValueError("this connector does not expose another page")
        return SourcePage(records=tuple(self.connector.fetch()))


class LiepinPagedAdapter:
    def __init__(self, connector) -> None:
        self.connector = connector

    def fetch_page(self, cursor: str | None) -> SourcePage:
        page_number = int(cursor) if cursor is not None else 0
        records, next_page = self.connector.fetch_page(page_number)
        return SourcePage(
            records=tuple(records),
            next_cursor=str(next_page) if next_page is not None else None,
        )


class NumericPagedAdapter:
    def __init__(self, connector, *, first_page: int = 1) -> None:
        self.connector = connector
        self.first_page = first_page

    def fetch_page(self, cursor: str | None) -> SourcePage:
        page_number = int(cursor) if cursor is not None else self.first_page
        records, next_page = self.connector.fetch_page(page_number)
        return SourcePage(
            records=tuple(records),
            next_cursor=str(next_page) if next_page is not None else None,
        )


class SerializedPageAdapter:
    """Consume already-sanitized pages produced by the Electron session bridge."""

    def __init__(self, pages: Sequence[SourcePage]) -> None:
        self.pages = tuple(pages)

    def fetch_page(self, cursor: str | None) -> SourcePage:
        index = int(cursor) if cursor is not None else 0
        if index < 0 or index >= len(self.pages):
            return SourcePage(records=())
        page = self.pages[index]
        return SourcePage(
            records=page.records,
            next_cursor=str(index + 1)
            if page.next_cursor is not None and index + 1 < len(self.pages)
            else page.next_cursor,
        )


class BudgetedSourceExecutor:
    def __init__(self, *, clock: Callable[[], float] = monotonic) -> None:
        self.clock = clock

    def run(
        self,
        adapter: PagedSourceAdapter,
        *,
        max_pages: int,
        time_budget_seconds: float,
        cursor: str | None = None,
    ) -> SourceExecutionResult:
        if not 1 <= max_pages <= 20:
            raise ValueError("max_pages must be between 1 and 20")
        if not 0.1 <= time_budget_seconds <= 120:
            raise ValueError("time budget must be between 0.1 and 120 seconds")
        started = self.clock()
        records: list[RawJobRecord] = []
        pages = 0
        next_cursor = cursor
        while pages < max_pages:
            if pages and self.clock() - started >= time_budget_seconds:
                return self._result(records, pages, started, next_cursor, "time_budget")
            page = adapter.fetch_page(next_cursor)
            pages += 1
            records.extend(page.records)
            next_cursor = page.next_cursor
            if next_cursor is None:
                return self._result(records, pages, started, None, "complete")
        return self._result(records, pages, started, next_cursor, "page_budget")

    def _result(
        self,
        records: list[RawJobRecord],
        pages: int,
        started: float,
        next_cursor: str | None,
        stop_reason: str,
    ) -> SourceExecutionResult:
        return SourceExecutionResult(
            records=tuple(records),
            pages_fetched=pages,
            elapsed_seconds=max(0.0, self.clock() - started),
            coverage_status="complete" if stop_reason == "complete" else "partial",
            can_continue=next_cursor is not None,
            next_cursor=next_cursor,
            stop_reason=stop_reason,
        )


class DesktopSearchService:
    def __init__(
        self,
        *,
        profiles: ResumeProfileService,
        sources: DesktopSourceService,
    ) -> None:
        self.profiles = profiles
        self.sources = sources

    def preflight(
        self,
        *,
        workspace_id: str,
        intent: str,
        source_ids: Sequence[str],
        max_pages: int = 3,
        time_budget_seconds: float = 15,
        resume_version_id: str | None = None,
    ) -> SearchPreflight:
        if self.profiles.active_draft_profile_id(workspace_id=workspace_id):
            raise SearchPreflightError(
                "resume import must be confirmed or abandoned before searching"
            )
        current = self.profiles.current_version(workspace_id=workspace_id)
        if resume_version_id is not None:
            current = next(
                (
                    version
                    for version in self.profiles.list_versions(
                        workspace_id=workspace_id
                    )
                    if version.version_id == resume_version_id
                ),
                None,
            )
            if current is None:
                raise SearchPreflightError(
                    "the requested resume version does not belong to this workspace"
                )
        keywords = build_search_keywords(intent=intent, resume=current)
        allowed: list[str] = []
        blocked: dict[str, str] = {}
        for source_id in dict.fromkeys(source_ids):
            try:
                self.sources.require_live_search(source_id)
            except (LookupError, SourceGateError) as error:
                blocked[source_id] = str(error)
            else:
                allowed.append(source_id)
        if not 1 <= max_pages <= 20:
            raise SearchPreflightError("max_pages must be between 1 and 20")
        if not 0.1 <= time_budget_seconds <= 120:
            raise SearchPreflightError(
                "time budget must be between 0.1 and 120 seconds"
            )
        return SearchPreflight(
            workspace_id=workspace_id,
            resume_version_id=current.version_id if current else None,
            keywords=keywords,
            allowed_source_ids=tuple(allowed),
            blocked_sources=blocked,
            max_pages=max_pages,
            time_budget_seconds=time_budget_seconds,
        )


def build_search_keywords(*, intent: str, resume) -> tuple[str, ...]:
    clean_intent = create_analysis_copy(
        source_version_id=resume.version_id if resume else "no-resume",
        text=" ".join(intent.split()),
    ).text
    clean_intent = _PRIVATE_PLACEHOLDER.sub("", clean_intent).strip()
    if not clean_intent:
        raise SearchPreflightError("a non-private job intent is required")
    if len(clean_intent) > 80:
        raise SearchPreflightError("job intent is too long")
    if resume is None:
        return (clean_intent,)

    terms: list[str] = []
    for value in resume.content.get("skills", ()):
        safe = create_analysis_copy(
            source_version_id=resume.version_id,
            text=value,
        ).text
        for term in _TERM_SPLIT.split(safe):
            normalized = term.strip()
            if 1 < len(normalized) <= 30 and "[已过滤:" not in normalized:
                terms.append(normalized)
    for section in ("projects", "experience"):
        for value in resume.content.get(section, ()):
            safe = create_analysis_copy(
                source_version_id=resume.version_id,
                text=value,
            ).text
            terms.extend(_TECH_TERM.findall(safe))
    unique_terms = tuple(dict.fromkeys(terms))[:6]
    queries = [
        " ".join((clean_intent, *unique_terms[:2])),
        clean_intent,
    ]
    queries.extend(f"{clean_intent} {term}" for term in unique_terms[2:3])
    return tuple(dict.fromkeys(queries))


def connector_adapter_for(*, source_id: str, keyword: str, city: str):
    if source_id == "company_12":
        from jobfindsme.connectors.deepseek_careers import DeepSeekCareersConnector

        return NumericPagedAdapter(
            DeepSeekCareersConnector(
                keyword, policy=ConnectorPolicy(public_access=True, robots_allowed=True)
            )
        )
    if source_id == "company_01":
        from jobfindsme.connectors.company_careers import TencentCareersConnector

        return NumericPagedAdapter(
            TencentCareersConnector(
                keyword,
                policy=ConnectorPolicy(public_access=True, robots_allowed=True),
            )
        )
    if source_id != "liepin":
        raise SourceGateError(
            "browser-backed sources require the Electron session bridge; "
            "legacy public CDP is not a production prerequisite"
        )
    from jobfindsme.connectors.pure_http import LiepinPureHttpConnector

    connector = LiepinPureHttpConnector(
        keyword,
        city=city,
        policy=ConnectorPolicy(public_access=True, robots_allowed=True),
        source_name="猎聘",
    )
    return LiepinPagedAdapter(connector)
