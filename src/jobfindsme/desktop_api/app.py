from __future__ import annotations

import hashlib
import hmac
import json
import threading
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from jobfindsme.app import jobfindsmecore
from jobfindsme.connectors import RawJobRecord
from jobfindsme.contracts import SourceKind
from jobfindsme.importing.normalizer import normalize_job
from jobfindsme.models import (
    CancellationToken,
    ModelCancelledError,
    ModelConnectionRepository,
    ModelGateway,
    ModelProtocol,
)
from jobfindsme.models.gateway import ConnectionStatus, ModelGatewayError
from jobfindsme.privacy import create_analysis_copy
from jobfindsme.profiles.models import ResumeImportMode
from jobfindsme.profiles.parser import ResumeExtractionError
from jobfindsme.profiles.service import ProfileError, ProfileNotFoundError
from jobfindsme.research import ResearchError, ResearchService
from jobfindsme.resume_editor import (
    PromptResumeEditor,
    PromptResumeError,
    ResumeEditorError,
)
from jobfindsme.scheduler import LocalScheduler
from jobfindsme.search.desktop import (
    BudgetedSourceExecutor,
    DesktopSearchService,
    SearchPreflightError,
    SerializedPageAdapter,
    SourcePage,
    connector_adapter_for,
)
from jobfindsme.search.jobs import DesktopJobFilters, DesktopJobService
from jobfindsme.search.matching_prompts import MatchingPromptService
from jobfindsme.sources.desktop import DesktopSourceService, SourceGateError


class StrictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictResponse):
    status: str


class WorkspaceSummary(StrictResponse):
    workspace_id: str
    name: str


class SourceCapability(StrictResponse):
    source_id: str
    source_type: str
    name: str
    login_required: bool
    live_search_enabled: bool
    session_status: str
    list_status: str
    detail_status: str
    fields_status: str
    pagination_status: str
    status: str
    detail: str
    last_verified_at: str | None


class BootstrapResponse(StrictResponse):
    product: str
    workspaces: list[WorkspaceSummary]
    sources: list[SourceCapability]


class DesktopSearchFilters(StrictResponse):
    cities: list[str] = Field(default_factory=list, max_length=20)
    salary_min_k: int | None = Field(default=None, ge=0, le=1000)
    salary_max_k: int | None = Field(default=None, ge=0, le=1000)
    salary_mode: str = "overlap"
    recruitment_track: str | None = None
    employment_type: str | None = None
    experience_min_years: int | None = Field(default=None, ge=0, le=80)
    experience_max_years: int | None = Field(default=None, ge=0, le=80)
    source_names: list[str] = Field(default_factory=list, max_length=20)
    read: str = "any"
    unknown_policy: str = "include"


class WorkspaceRequest(StrictResponse):
    workspace_id: str


class SearchPreferencesRequest(StrictResponse):
    workspace_id: str
    target_role: str = Field(default="", max_length=120)
    cities: list[str] = Field(default_factory=list, max_length=20)
    salary_min_k: int | None = Field(default=None, ge=0, le=1000)
    salary_max_k: int | None = Field(default=None, ge=0, le=1000)


class RefilterRequest(StrictResponse):
    workspace_id: str
    filters: DesktopSearchFilters
    page_size: Literal[10, 20, 50] = 10


class BrowserSourceRecord(StrictResponse):
    external_id: str = Field(min_length=1, max_length=500)
    source_name: str = Field(min_length=1, max_length=80)
    source_url: str = Field(min_length=1, max_length=2000)
    payload: dict


class BrowserCollection(StrictResponse):
    batches: int = Field(ge=0, le=3)
    elapsed_seconds: float = Field(ge=0, le=180)
    stop_reason: str = Field(max_length=100)
    cursor: str | None = Field(default=None, max_length=200)
    complete: bool = False
    failure: Literal["risk_control", "login_required"] | None = None


class BrowserSourcePage(StrictResponse):
    collection: BrowserCollection | None = None
    records: list[BrowserSourceRecord] = Field(default_factory=list, max_length=100)
    next_cursor: str | None = Field(default=None, max_length=200)


class SearchPreflightRequest(StrictResponse):
    workspace_id: str
    intent: str = Field(default="", max_length=80)
    source_ids: list[str] = Field(default_factory=lambda: ["liepin"], max_length=20)
    city: str = Field(default="", max_length=30)
    max_pages: int = Field(default=3, ge=1, le=20)
    time_budget_seconds: float = Field(default=15, ge=0.1, le=120)
    filters: DesktopSearchFilters = Field(default_factory=DesktopSearchFilters)
    weights: dict[str, int] | None = None
    rule_version_id: str | None = None
    browser_pages: dict[str, list[BrowserSourcePage]] = Field(
        default_factory=dict, max_length=20
    )
    browser_errors: dict[str, str] = Field(default_factory=dict, max_length=20)
    page_size: int = 20
    resume_version_id: str | None = None


class PublicSourcePagesRequest(StrictResponse):
    keyword: str = Field(min_length=1, max_length=120)
    city: str = Field(default="", max_length=30)
    max_pages: int = Field(default=2, ge=1, le=3)
    seconds: float = Field(default=15, ge=1, le=60)
    force_refresh: bool = False


class SourceVerificationRequest(StrictResponse):
    session_status: str
    list_status: str
    detail_status: str
    fields_status: str
    pagination_status: str
    enabled: bool
    notes: str = Field(max_length=1000)


class SourceRuntimeFailureRequest(StrictResponse):
    failure: str = Field(pattern="^(login_required|risk_control)$")
    notes: str = Field(min_length=1, max_length=1000)


class SearchPreflightResponse(StrictResponse):
    workspace_id: str
    resume_version_id: str | None
    keywords: list[str]
    allowed_source_ids: list[str]
    blocked_sources: dict[str, str]
    max_pages: int
    time_budget_seconds: float


class MatchingRuleRequest(StrictResponse):
    workspace_id: str
    name: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=1, max_length=6000)
    template_id: str = Field(default="custom", max_length=80)
    mode: Literal["local", "model"] = "local"
    connection_id: str | None = None
    candidate_limit: int = Field(default=20, ge=1, le=20)
    weights: dict[str, int]


class MatchingRerankRequest(StrictResponse):
    workspace_id: str
    run_id: str
    request_id: str = Field(min_length=16, max_length=128)
    api_key: str = Field(default="", max_length=4096)


class MatchingTrialRequest(StrictResponse):
    workspace_id: str
    job_id: str
    rule_version_id: str


class MatchingPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str
    job_id: str
    weights: dict[str, int]


class SourceSearchRunResponse(StrictResponse):
    source_id: str
    status: str
    pages_fetched: int
    elapsed_seconds: float
    coverage_status: str
    can_continue: bool
    next_cursor: str | None
    stop_reason: str
    error: str | None = None


class SourceSearchJobResponse(StrictResponse):
    source_id: str
    source_name: str
    external_id: str
    payload: dict


class SourceSearchResponse(SearchPreflightResponse):
    jobs: list[SourceSearchJobResponse]
    source_runs: list[SourceSearchRunResponse]
    result_page: dict


class JobTrackingRequest(StrictResponse):
    workspace_id: str
    event_type: str
    enabled: bool = True


class JobTrackingResponse(StrictResponse):
    read: bool
    saved: bool
    applied: bool


class ResumeCapabilities(StrictResponse):
    supported_formats: list[str]
    doc_status: str
    ocr_status: str
    detail: str


class ResumeFactResponse(StrictResponse):
    fact_id: str
    fact_type: str
    value: str
    status: str


class ResumeResponse(StrictResponse):
    workspace_id: str
    profile_id: str
    document_id: str
    status: str
    file_name: str
    facts: list[ResumeFactResponse]


class ResumeStateResponse(StrictResponse):
    workspace_id: str | None
    pending_confirmation: bool
    current_version_id: str | None
    current_version_number: int | None
    search_profile_state: str
    search_block_reason: str | None
    active_draft: ResumeResponse | None
    capabilities: ResumeCapabilities


class ResumeImportRequest(StrictResponse):
    source_path: str
    workspace_id: str | None = None
    mode: ResumeImportMode = ResumeImportMode.MANAGED


class ResumeConfirmationRequest(StrictResponse):
    workspace_id: str
    accepted_fact_ids: list[str]
    corrections: dict[str, str] = Field(default_factory=dict)


class AnalysisPreviewRequest(StrictResponse):
    workspace_id: str
    privacy_mode: str = "redact"
    redacted_fields: list[str] | None = None


class AnalysisPreviewResponse(StrictResponse):
    source_version_id: str
    redacted_fields: list[str]
    text: str
    limitations: str


class ResumeVersionResponse(StrictResponse):
    version_id: str
    parent_version_id: str | None
    version_number: int
    content: dict[str, list[str]]
    is_current: bool
    created_at: str


class ResumeEditRequest(StrictResponse):
    workspace_id: str
    base_version_id: str
    content: dict[str, list[str]]


class ResumeRestoreRequest(StrictResponse):
    workspace_id: str


class ResumeExportRequest(StrictResponse):
    workspace_id: str
    destination: str
    format: str
    template: str


class ResumeExportResponse(StrictResponse):
    path: str
    format: str
    template: str
    version_id: str


class PromptSessionRequest(StrictResponse):
    target_title: str = Field(default="", max_length=300)
    target_url: str = Field(default="", max_length=2000)
    target_jd: str = Field(default="", max_length=30000)
    workspace_id: str
    base_version_id: str
    connection_id: str


class PromptTurnRequest(StrictResponse):
    request_id: str = Field(min_length=16, max_length=128)
    api_key: str = Field(max_length=4096)
    prompt: str = Field(min_length=1, max_length=4000)
    project_facts: list[str] = Field(default_factory=list, max_length=100)
    optional_jd: str | None = Field(default=None, max_length=30000)
    redacted_fields: list[str] | None = None


class PatchDecisionRequest(StrictResponse):
    decision: str


class PromptPatchResponse(StrictResponse):
    patch_id: str
    turn_number: int
    section: str
    before: list[str]
    after: list[str]
    rationale: str
    evidence_ids: list[str]
    needs_user_input: list[str]
    status: str


class PromptSessionResponse(StrictResponse):
    messages: list[dict] = Field(default_factory=list)
    target_title: str = ""
    target_url: str = ""
    target_jd: str = ""
    saved_version_id: str | None = None
    session_id: str
    workspace_id: str
    base_version_id: str
    connection_id: str
    status: str
    patches: list[PromptPatchResponse]


class ModelConnectionRequest(StrictResponse):
    connection_id: str | None = None
    provider: str
    protocol: ModelProtocol
    endpoint: str
    model_id: str
    credential_ref: str | None = None
    auth_mode: Literal["api_key", "none"] = "api_key"


class ModelConnectionResponse(StrictResponse):
    connection_id: str
    provider: str
    protocol: str
    endpoint: str
    model_id: str
    status: str
    last_error: str | None
    last_tested_at: str | None
    input_tokens: int | None
    output_tokens: int | None
    credential_ref: str | None
    auth_mode: str


class ModelTestRequest(StrictResponse):
    test_id: str = Field(min_length=16, max_length=128)
    api_key: str = Field(max_length=4096)
    timeout_seconds: float = Field(default=15, ge=1, le=120)


class ResearchEvidenceInput(StrictResponse):
    url: str | None = Field(default=None, max_length=2000)
    platform: str = Field(default="用户提供", max_length=80)
    published_at: str | None = None
    excerpt: str = Field(min_length=1, max_length=2000)
    relevance: str = "company"


class ResearchJobRequest(StrictResponse):
    workspace_id: str
    url: str = Field(max_length=2000)
    title: str = Field(min_length=1, max_length=300)
    company: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=30, max_length=30000)


class BossDetailRequest(ResearchJobRequest):
    location: str = Field(default="", max_length=200)
    salary: str = Field(default="", max_length=100)
    company: str = Field(default="", max_length=300)
    fetched_at: datetime


class ResearchCorrectionRequest(StrictResponse):
    workspace_id: str
    evidence_id: str
    kind: Literal["wrong_entity", "broken_link", "wrong_team", "other"]
    note: str = Field(default="", max_length=1000)


class ResearchRunRequest(StrictResponse):
    context_company: str | None = Field(default=None, max_length=300)
    context_description: str | None = Field(default=None, max_length=30000)
    interest_question: str | None = Field(default=None, max_length=300)
    topics: list[Literal["company", "job"]] = Field(default_factory=list, max_length=2)
    workspace_id: str
    job_id: str
    resume_version_id: str | None = None
    team: str | None = Field(default=None, max_length=160)
    directions: list[Literal["role", "workload", "leave", "care"]] = Field(
        default_factory=lambda: ["role", "workload", "leave", "care"],
        min_length=0,
        max_length=5,
    )
    source_ids: list[str] = Field(
        default_factory=lambda: ["official", "maimai", "kanzhun", "zhihu", "offershow"],
        max_length=8,
    )
    user_evidence: list[ResearchEvidenceInput] = Field(
        default_factory=list, max_length=20
    )
    connection_id: str | None = None
    request_id: str | None = Field(default=None, min_length=16, max_length=128)
    api_key: str | None = Field(default=None, max_length=4096)


class ScheduledTaskRequest(StrictResponse):
    workspace_id: str
    name: str = Field(min_length=1, max_length=120)
    intent: str = Field(min_length=1, max_length=80)
    source_ids: list[str] = Field(min_length=1, max_length=20)
    filters: DesktopSearchFilters = Field(default_factory=DesktopSearchFilters)
    weights: dict[str, int] | None = None
    frequency: str
    timezone: str = Field(min_length=1, max_length=80)
    local_time: str | None = None
    weekday: int | None = None
    interval_minutes: int | None = None
    catch_up_policy: str = "once"


class RunDueTasksRequest(StrictResponse):
    matching_keys_by_task: dict[str, str] = Field(default_factory=dict, max_length=100)
    browser_pages_by_task: dict[str, dict[str, list[BrowserSourcePage]]] = Field(
        default_factory=dict, max_length=100
    )
    browser_errors_by_task: dict[str, dict[str, str]] = Field(
        default_factory=dict, max_length=100
    )


def _authorization_dependency(token: str) -> Callable[..., None]:
    def require_token(authorization: str | None = Header(default=None)) -> None:
        scheme, _, credential = (authorization or "").partition(" ")
        valid = (
            scheme.casefold() == "bearer"
            and bool(credential)
            and hmac.compare_digest(credential, token)
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid desktop API credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return require_token


def _source_capability_payload(item) -> SourceCapability:
    return SourceCapability(
        source_id=item.source_id,
        source_type=item.source_type,
        name=item.name,
        login_required=item.login_required,
        live_search_enabled=item.live_search_enabled,
        session_status=item.session_status,
        list_status=item.list_status,
        detail_status=item.detail_status,
        fields_status=item.fields_status,
        pagination_status=item.pagination_status,
        status=("available" if item.live_search_enabled else "restricted"),
        detail=item.notes,
        last_verified_at=item.last_verified_at,
    )


def create_app(
    *,
    token: str,
    database_path: str | Path,
    model_gateway_override: ModelGateway | None = None,
    source_adapter_factory_override=None,
    research_evidence_search_override=None,
    scheduler_clock_override=None,
) -> FastAPI:
    if not token:
        raise ValueError("desktop API token must not be empty")

    core = jobfindsmecore(database_path)
    model_connections = ModelConnectionRepository(core.database)
    model_gateway = model_gateway_override or ModelGateway()
    prompt_editor = PromptResumeEditor(core.database, core.resume_editor, model_gateway)
    desktop_sources = DesktopSourceService(core.database)
    desktop_search = DesktopSearchService(
        profiles=core.profiles,
        sources=desktop_sources,
    )
    desktop_jobs = DesktopJobService(core.database, core.jobs)
    matching = MatchingPromptService(
        core.database, desktop_jobs, model_connections, model_gateway
    )
    matching_requests: dict[str, tuple[str, CancellationToken]] = {}
    matching_lock = threading.Lock()
    cancelled_matching: dict[str, str] = {}
    research = ResearchService(
        core.database,
        core.jobs,
        core.profiles,
        research_evidence_search_override,
    )
    scheduler = LocalScheduler(core.database, clock=scheduler_clock_override)
    source_executor = BudgetedSourceExecutor()
    source_adapter_factory = source_adapter_factory_override or (
        lambda source_id, keyword, city: connector_adapter_for(
            source_id=source_id, keyword=keyword, city=city
        )
    )
    active_model_tests: dict[str, tuple[str, CancellationToken]] = {}
    active_model_tests_lock = threading.Lock()
    active_prompt_requests: dict[str, tuple[str, CancellationToken]] = {}
    active_prompt_requests_lock = threading.Lock()
    active_research_requests: dict[str, tuple[str, CancellationToken]] = {}
    active_research_requests_lock = threading.Lock()
    require_token = _authorization_dependency(token)
    app = FastAPI(
        title="JobFindsMe Desktop API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get(
        "/health",
        response_model=HealthResponse,
        dependencies=[Depends(require_token)],
    )
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get(
        "/v1/bootstrap",
        response_model=BootstrapResponse,
        dependencies=[Depends(require_token)],
    )
    def bootstrap() -> BootstrapResponse:
        if not core.list_workspaces():
            core.create_workspace("我的求职工作区")
        workspaces = [
            WorkspaceSummary(workspace_id=item.workspace_id, name=item.name)
            for item in core.list_workspaces()
        ]
        return BootstrapResponse(
            product="JobFindsMe",
            workspaces=workspaces,
            sources=[
                _source_capability_payload(item) for item in desktop_sources.list()
            ],
        )

    public_pages_cache: dict = {}
    public_pages_failures: dict = {}
    public_pages_lock = threading.Lock()

    @app.post(
        "/v1/sources/{source_id}/public-pages", dependencies=[Depends(require_token)]
    )
    def public_source_pages(source_id: str, request: PublicSourcePagesRequest):
        # Only proven anonymous adapters may run before a capability check.
        if source_id not in {"liepin", "company_01", "company_12"}:
            raise HTTPException(status_code=409, detail="no_public_adapter")
        import time

        key = (
            source_id,
            request.keyword,
            request.city,
            request.max_pages,
            request.seconds,
        )
        with public_pages_lock:
            cached = public_pages_cache.get(key)
            if (
                not request.force_refresh
                and cached
                and time.monotonic() - cached[0] < 120
            ):
                return cached[1]
            failure = public_pages_failures.get(source_id)
            if failure and time.monotonic() - failure[0] < 300:
                raise HTTPException(status_code=failure[1], detail=failure[2])
            adapter = source_adapter_factory(source_id, request.keyword, request.city)
            pages, cursor, started = [], None, time.monotonic()
            try:
                for _ in range(request.max_pages):
                    if pages and time.monotonic() - started > request.seconds:
                        break
                    page = adapter.fetch_page(cursor)
                    pages.append(
                        {
                            "records": [
                                {
                                    "external_id": r.external_id,
                                    "source_name": r.source_name,
                                    "source_url": r.source_url,
                                    "payload": dict(r.payload),
                                }
                                for r in page.records[:100]
                            ],
                            "next_cursor": page.next_cursor,
                        }
                    )
                    cursor = page.next_cursor
                    if cursor is None:
                        break
            except Exception as error:
                message = str(error)[:500]
                risky = any(
                    marker in message.lower()
                    for marker in (
                        "429",
                        "403",
                        "captcha",
                        "risk_control",
                        "验证码",
                        "访问过于频繁",
                    )
                )
                code = 429 if risky else 502
                public_pages_failures[source_id] = (time.monotonic(), code, message)
                if not pages:
                    raise HTTPException(status_code=code, detail=message) from error
            if pages:
                pages[-1]["next_cursor"] = None
                pages[-1]["collection"] = {
                    "batches": len(pages),
                    "elapsed_seconds": min(180, time.monotonic() - started),
                    "stop_reason": "complete" if cursor is None else "page_budget",
                    "cursor": None,
                    "complete": cursor is None,
                    "failure": None,
                }
            public_pages_cache[key] = (time.monotonic(), pages)
            if len(public_pages_cache) > 40:
                public_pages_cache.pop(next(iter(public_pages_cache)))
            return pages

    @app.put(
        "/v1/sources/{source_id}/verification",
        response_model=SourceCapability,
        dependencies=[Depends(require_token)],
    )
    def record_source_verification(
        source_id: str, request: SourceVerificationRequest
    ) -> SourceCapability:
        try:
            source = desktop_sources.record_verification(
                source_id=source_id,
                **request.model_dump(),
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail="source not found") from error
        except (ValueError, PermissionError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _source_capability_payload(source)

    @app.post(
        "/v1/sources/{source_id}/runtime-failure",
        response_model=SourceCapability,
        dependencies=[Depends(require_token)],
    )
    def record_source_runtime_failure(
        source_id: str, request: SourceRuntimeFailureRequest
    ) -> SourceCapability:
        try:
            source = desktop_sources.record_runtime_failure(
                source_id=source_id,
                failure=request.failure,
                notes=request.notes,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail="source not found") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _source_capability_payload(source)

    @app.post(
        "/v1/search-preflight",
        response_model=SearchPreflightResponse,
        dependencies=[Depends(require_token)],
    )
    def search_preflight(request: SearchPreflightRequest) -> SearchPreflightResponse:
        try:
            preflight = desktop_search.preflight(
                workspace_id=request.workspace_id,
                intent=request.intent,
                source_ids=request.source_ids,
                max_pages=request.max_pages,
                time_budget_seconds=request.time_budget_seconds,
                resume_version_id=request.resume_version_id,
            )
        except SearchPreflightError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _preflight_payload(preflight)

    @app.post(
        "/v1/source-searches",
        response_model=SourceSearchResponse,
        dependencies=[Depends(require_token)],
    )
    def run_source_search(request: SearchPreflightRequest) -> SourceSearchResponse:
        try:
            preflight = desktop_search.preflight(
                workspace_id=request.workspace_id,
                intent=request.intent,
                source_ids=request.source_ids,
                max_pages=request.max_pages,
                time_budget_seconds=request.time_budget_seconds,
                resume_version_id=request.resume_version_id,
            )
        except SearchPreflightError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        jobs: list[SourceSearchJobResponse] = []
        snapshot_job_ids: list[str] = []
        runs: list[SourceSearchRunResponse] = []
        for source_id in preflight.allowed_source_ids:
            browser_error = request.browser_errors.get(source_id)
            if browser_error:
                runs.append(
                    SourceSearchRunResponse(
                        source_id=source_id,
                        status="failed",
                        pages_fetched=0,
                        elapsed_seconds=0,
                        coverage_status="failed",
                        can_continue=False,
                        next_cursor=None,
                        stop_reason="browser_session_error",
                        error=browser_error,
                    )
                )
                continue
            try:
                serialized = request.browser_pages.get(source_id)
                adapter = (
                    SerializedPageAdapter(
                        [
                            SourcePage(
                                records=tuple(
                                    RawJobRecord(
                                        source_kind=SourceKind.CAREER_SITE,
                                        source_name=item.source_name,
                                        source_url=item.source_url,
                                        external_id=item.external_id,
                                        payload=item.payload,
                                    )
                                    for item in page.records
                                ),
                                next_cursor=page.next_cursor,
                            )
                            for page in serialized
                        ]
                    )
                    if serialized is not None
                    else source_adapter_factory(
                        source_id, preflight.keywords[0], request.city
                    )
                )
                result = source_executor.run(
                    adapter,
                    max_pages=preflight.max_pages,
                    time_budget_seconds=preflight.time_budget_seconds,
                )
            except Exception as error:
                runs.append(
                    SourceSearchRunResponse(
                        source_id=source_id,
                        status="failed",
                        pages_fetched=0,
                        elapsed_seconds=0,
                        coverage_status="failed",
                        can_continue=False,
                        next_cursor=None,
                        stop_reason="connector_error",
                        error=str(error),
                    )
                )
                continue
            normalization_errors = 0
            for record in result.records[:100]:
                try:
                    normalized = normalize_job(record)
                    core.jobs.upsert(request.workspace_id, normalized)
                except (ValueError, TypeError, KeyError):
                    normalization_errors += 1
                    continue
                snapshot_job_ids.append(normalized.job_id)
                jobs.append(
                    SourceSearchJobResponse(
                        source_id=source_id,
                        source_name=record.source_name,
                        external_id=record.external_id,
                        payload=dict(record.payload),
                    )
                )
            collection = serialized[-1].collection if serialized else None
            runs.append(
                SourceSearchRunResponse(
                    source_id=source_id,
                    status="partial"
                    if normalization_errors
                    else (
                        (
                            "success"
                            if collection.complete
                            else "partial"
                            if result.records
                            else "failed"
                        )
                        if collection
                        else "success"
                    ),
                    pages_fetched=collection.batches
                    if collection
                    else result.pages_fetched,
                    elapsed_seconds=collection.elapsed_seconds
                    if collection
                    else result.elapsed_seconds,
                    coverage_status="partial"
                    if normalization_errors
                    else (
                        ("complete" if collection.complete else "partial")
                        if collection
                        else result.coverage_status
                    ),
                    can_continue=bool(collection.cursor)
                    if collection
                    else result.can_continue,
                    next_cursor=collection.cursor if collection else result.next_cursor,
                    stop_reason="invalid_records"
                    if normalization_errors
                    else (collection.stop_reason if collection else result.stop_reason),
                )
            )
            # Save already-read rows before disabling the source, so risk/cancellation
            # never discards partial results and future requests still respect the gate.
            if collection and collection.failure:
                desktop_sources.record_runtime_failure(
                    source_id=source_id,
                    failure=collection.failure,
                    notes="平台要求重新登录或验证；已保留本次读取的岗位。",
                )
        try:
            filters = DesktopJobFilters(
                cities=tuple(request.filters.cities),
                salary_min_k=request.filters.salary_min_k,
                salary_max_k=request.filters.salary_max_k,
                salary_mode=request.filters.salary_mode,
                recruitment_track=request.filters.recruitment_track,
                employment_type=request.filters.employment_type,
                experience_min_years=request.filters.experience_min_years,
                experience_max_years=request.filters.experience_max_years,
                source_names=tuple(request.filters.source_names),
                read=request.filters.read,
                unknown_policy=request.filters.unknown_policy,
            )
            current_resume = next(
                (
                    version
                    for version in core.profiles.list_versions(
                        workspace_id=request.workspace_id
                    )
                    if version.version_id == preflight.resume_version_id
                ),
                None,
            )
            run_id = desktop_jobs.create_snapshot(
                workspace_id=request.workspace_id,
                intent=request.intent.strip() or preflight.keywords[0],
                job_ids=snapshot_job_ids,
                resume_version=current_resume,
                filters=filters,
                weights=request.weights,
                rule_version_id=request.rule_version_id,
            )
            result_page = desktop_jobs.page(
                workspace_id=request.workspace_id,
                run_id=run_id,
                page=1,
                page_size=request.page_size,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return SourceSearchResponse(
            **_preflight_payload(preflight).model_dump(),
            jobs=jobs,
            source_runs=runs,
            result_page=result_page,
        )

    @app.get("/v1/matching-rules", dependencies=[Depends(require_token)])
    def matching_rules(workspace_id: str) -> dict:
        return matching.state(workspace_id)

    @app.post("/v1/matching-rules", dependencies=[Depends(require_token)])
    def save_matching_rule(request: MatchingRuleRequest) -> dict:
        try:
            return matching.save(**request.model_dump())
        except (ValueError, LookupError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.delete(
        "/v1/matching-rules/{rule_version_id}", dependencies=[Depends(require_token)]
    )
    def delete_matching_rule(rule_version_id: str, workspace_id: str) -> dict:
        try:
            matching.delete_version(workspace_id, rule_version_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"deleted": True}

    @app.post("/v1/matching-trials", dependencies=[Depends(require_token)])
    def matching_trial(request: MatchingTrialRequest) -> dict:
        try:
            resume = core.profiles.current_version(workspace_id=request.workspace_id)
            if resume is None:
                raise ValueError("请先确认简历；尚未评分")
            core.jobs.get(workspace_id=request.workspace_id, job_id=request.job_id)
            run = desktop_jobs.create_snapshot(
                workspace_id=request.workspace_id,
                intent="匹配试算",
                job_ids=[request.job_id],
                resume_version=resume,
                filters=DesktopJobFilters(),
                rule_version_id=request.rule_version_id,
            )
            return desktop_jobs.page(
                workspace_id=request.workspace_id, run_id=run, page=1, page_size=10
            )
        except (ValueError, LookupError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/v1/matching-input", dependencies=[Depends(require_token)])
    def matching_input(workspace_id: str, run_id: str) -> dict:
        try:
            _, rule, payload = matching.input_for_run(workspace_id, run_id)
            return {"rule": rule, "payload": payload}
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/v1/matching-rerank", dependencies=[Depends(require_token)])
    def matching_rerank(request: MatchingRerankRequest) -> dict:
        cancellation = CancellationToken()
        with matching_lock:
            if request.request_id in matching_requests:
                raise HTTPException(status_code=409, detail="重复请求")
            if cancelled_matching.pop(request.request_id, None) == request.workspace_id:
                cancellation.cancel()
            matching_requests[request.request_id] = (request.workspace_id, cancellation)
        try:
            return matching.rerank(
                request.workspace_id,
                request.run_id,
                api_key=request.api_key,
                cancellation=cancellation,
            )
        except ModelCancelledError:
            return {
                "status": "cancelled",
                "message": "已取消，保留本地结果；服务商可能已产生用量。",
            }
        except (ValueError, LookupError, ModelGatewayError):
            return {
                "status": "failed",
                "message": "模型连接或证据校验失败，保留本地结果。",
            }
        finally:
            with matching_lock:
                matching_requests.pop(request.request_id, None)

    @app.post("/v1/matching-cancel", dependencies=[Depends(require_token)])
    def matching_cancel(workspace_id: str, request_id: str) -> dict:
        with matching_lock:
            active = matching_requests.get(request_id)
            if active and active[0] == workspace_id:
                active[1].cancel()
            elif not active:
                if len(cancelled_matching) >= 256:
                    cancelled_matching.pop(next(iter(cancelled_matching)))
                cancelled_matching[request_id] = workspace_id
        return {"cancelled": True}

    @app.post("/v1/matching-preview", dependencies=[Depends(require_token)])
    def matching_preview(request: MatchingPreviewRequest) -> dict:
        from jobfindsme.search.rules import DEFAULT_WEIGHTS, evaluate

        try:
            weights = desktop_jobs._validate_weights(request.weights)
            if set(weights) != set(DEFAULT_WEIGHTS):
                raise ValueError("preview requires the four current dimensions")
            job = core.jobs.get(
                workspace_id=request.workspace_id, job_id=request.job_id
            )
            resume = core.profiles.current_version(workspace_id=request.workspace_id)
            return {
                **evaluate(job, resume, weights),
                "job_id": job.job_id,
                "resume_version_id": resume.version_id if resume else None,
            }
        except LookupError as error:
            raise HTTPException(status_code=404, detail="job not found") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post(
        "/v1/search-runs/{run_id}/refilter", dependencies=[Depends(require_token)]
    )
    def refilter_run(run_id: str, request: RefilterRequest) -> dict:
        with core.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM desktop_search_runs WHERE run_id=? AND workspace_id=?",
                (run_id, request.workspace_id),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="search run not found")
        resume = next(
            (
                v
                for v in core.profiles.list_versions(workspace_id=request.workspace_id)
                if v.version_id == row["resume_version_id"]
            ),
            None,
        )
        if row["resume_version_id"] and resume is None:
            raise HTTPException(status_code=409, detail="resume snapshot unavailable")
        try:
            filtered = desktop_jobs.create_snapshot(
                workspace_id=request.workspace_id,
                intent=row["intent"],
                job_ids=json.loads(row["candidate_job_ids_json"])
                or json.loads(row["ordered_job_ids_json"]),
                resume_version=resume,
                filters=DesktopJobFilters(**request.filters.model_dump()),
                rule_version_id=row["rule_version_id"],
            )
            if row["rerank_json"]:
                # Refiltering never calls a model or silently discards its prior scores.
                with core.database.connect() as connection:
                    derived = connection.execute(
                        "SELECT scores_json FROM desktop_search_runs WHERE run_id=?",
                        (filtered,),
                    ).fetchone()
                    scores = json.loads(derived["scores_json"])
                    previous = json.loads(row["scores_json"])
                    model_ids = [
                        job_id
                        for job_id in json.loads(row["ordered_job_ids_json"])
                        if job_id in scores and previous[job_id].get("model_match")
                    ]
                    for job_id in model_ids:
                        scores[job_id] = previous[job_id]
                    ordered = model_ids + sorted(
                        (job_id for job_id in scores if job_id not in model_ids),
                        key=lambda job_id: (-scores[job_id]["score"], job_id),
                    )
                    meta = json.loads(row["rerank_json"])
                    meta.update(
                        total=len(scores),
                        candidate_count=len(model_ids),
                        scored_count=sum(
                            scores[job_id]["model_match"].get("score") is not None
                            for job_id in model_ids
                        ),
                    )
                    connection.execute(
                        "UPDATE desktop_search_runs SET ordered_job_ids_json=?,"
                        "scores_json=?,rerank_json=? WHERE run_id=?",
                        (
                            json.dumps(ordered),
                            json.dumps(scores, ensure_ascii=False),
                            json.dumps(meta),
                            filtered,
                        ),
                    )
            return desktop_jobs.page(
                workspace_id=request.workspace_id,
                run_id=filtered,
                page=1,
                page_size=request.page_size,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get(
        "/v1/search-runs/{run_id}/jobs",
        dependencies=[Depends(require_token)],
    )
    def search_run_page(
        run_id: str, workspace_id: str, page: int = 1, page_size: int = 20
    ) -> dict:
        try:
            return desktop_jobs.page(
                workspace_id=workspace_id,
                run_id=run_id,
                page=page,
                page_size=page_size,
            )
        except LookupError as error:
            raise HTTPException(
                status_code=404, detail="search run not found"
            ) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post(
        "/v1/jobs/{job_id}/events",
        response_model=JobTrackingResponse,
        dependencies=[Depends(require_token)],
    )
    def record_job_event(
        job_id: str, request: JobTrackingRequest
    ) -> JobTrackingResponse:
        if request.event_type not in {"read", "saved", "applied", "apply_opened"}:
            raise HTTPException(status_code=400, detail="invalid job event type")
        try:
            value = desktop_jobs.set_tracking(
                workspace_id=request.workspace_id,
                job_id=job_id,
                event_type=request.event_type,
                enabled=request.enabled,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail="job not found") from error
        return JobTrackingResponse(**asdict(value))

    @app.get(
        "/v1/job-tracking",
        dependencies=[Depends(require_token)],
    )
    def list_job_tracking(workspace_id: str) -> list[dict]:
        return desktop_jobs.list_tracking(workspace_id)

    def resolve_workspace(workspace_id: str | None, *, create: bool = False):
        if workspace_id:
            return core.context.resolve_workspace(workspace_id)
        workspaces = core.list_workspaces()
        if workspaces:
            return workspaces[0]
        if create:
            return core.create_workspace("我的求职工作区")
        return None

    def resume_payload(workspace_id: str, profile_id: str) -> ResumeResponse:
        profile = core.profiles.load_review(
            workspace_id=workspace_id,
            profile_id=profile_id,
        )
        document = core.profiles.load_document(
            workspace_id=workspace_id,
            document_id=profile.document_id,
        )
        return ResumeResponse(
            workspace_id=workspace_id,
            profile_id=profile.profile_id,
            document_id=profile.document_id,
            status=profile.status.value,
            file_name=document.file_name,
            facts=[
                ResumeFactResponse(
                    fact_id=fact.fact_id,
                    fact_type=fact.fact_type.value,
                    value=fact.value,
                    status=fact.status.value,
                )
                for fact in profile.facts
            ],
        )

    @app.get("/v1/search-preferences", dependencies=[Depends(require_token)])
    def get_search_preferences(workspace_id: str) -> dict:
        try:
            resolve_workspace(workspace_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail="workspace not found") from error
        with core.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM desktop_search_preferences WHERE workspace_id=?",
                (workspace_id,),
            ).fetchone()
        return {
            "workspace_id": workspace_id,
            "target_role": row["target_role"] if row else "",
            "cities": json.loads(row["cities_json"]) if row else [],
            "salary_min_k": row["salary_min_k"] if row else None,
            "salary_max_k": row["salary_max_k"] if row else None,
        }

    @app.put("/v1/search-preferences", dependencies=[Depends(require_token)])
    def save_search_preferences(request: SearchPreferencesRequest) -> dict:
        try:
            resolve_workspace(request.workspace_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail="workspace not found") from error
        if request.salary_min_k is not None and request.salary_max_k is not None and request.salary_min_k > request.salary_max_k:
            raise HTTPException(status_code=400, detail="最低期望薪资不能高于最高期望薪资")
        cities = list(dict.fromkeys(city.strip() for city in request.cities if city.strip()))
        if any(len(city) > 80 for city in cities):
            raise HTTPException(status_code=400, detail="城市名称过长")
        with core.database.connect() as connection:
            connection.execute(
                """INSERT INTO desktop_search_preferences
                (workspace_id,target_role,cities_json,salary_min_k,salary_max_k,updated_at)
                VALUES (?,?,?,?,?,?) ON CONFLICT(workspace_id) DO UPDATE SET
                target_role=excluded.target_role,cities_json=excluded.cities_json,
                salary_min_k=excluded.salary_min_k,salary_max_k=excluded.salary_max_k,
                updated_at=excluded.updated_at""",
                (request.workspace_id, request.target_role.strip(), json.dumps(cities, ensure_ascii=False), request.salary_min_k, request.salary_max_k, datetime.now(UTC).isoformat()),
            )
        return get_search_preferences(request.workspace_id)

    @app.get(
        "/v1/resumes/state",
        response_model=ResumeStateResponse,
        dependencies=[Depends(require_token)],
    )
    def resume_state(workspace_id: str | None = None) -> ResumeStateResponse:
        workspace = resolve_workspace(workspace_id)
        if workspace is None:
            return ResumeStateResponse(
                workspace_id=None,
                pending_confirmation=False,
                current_version_id=None,
                current_version_number=None,
                search_profile_state="no_resume",
                search_block_reason=None,
                active_draft=None,
                capabilities=_resume_capabilities(),
            )
        active_profile_id = core.profiles.active_draft_profile_id(
            workspace_id=workspace.workspace_id
        )
        active_draft = (
            resume_payload(workspace.workspace_id, active_profile_id)
            if active_profile_id
            else None
        )
        current = core.profiles.current_version(workspace_id=workspace.workspace_id)
        return ResumeStateResponse(
            workspace_id=workspace.workspace_id,
            pending_confirmation=active_draft is not None,
            current_version_id=current.version_id if current else None,
            current_version_number=current.version_number if current else None,
            search_profile_state=(
                "pending_confirmation"
                if active_draft is not None
                else "ready"
                if current is not None
                else "no_resume"
            ),
            search_block_reason=(
                "resume import must be confirmed before searching"
                if active_draft is not None
                else None
            ),
            active_draft=active_draft,
            capabilities=_resume_capabilities(),
        )

    @app.post("/v1/resumes/clear-current", dependencies=[Depends(require_token)])
    def clear_current_resume(request: WorkspaceRequest) -> ResumeStateResponse:
        try:
            resolve_workspace(request.workspace_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail="workspace not found") from error
        core.profiles.clear_current(workspace_id=request.workspace_id)
        return resume_state(request.workspace_id)

    @app.post(
        "/v1/resumes/import",
        response_model=ResumeResponse,
        dependencies=[Depends(require_token)],
    )
    def import_resume(request: ResumeImportRequest) -> ResumeResponse:
        workspace = resolve_workspace(request.workspace_id, create=True)
        try:
            profile = core.profiles.import_resume(
                workspace_id=workspace.workspace_id,
                source_path=request.source_path,
                mode=request.mode,
            )
        except (OSError, ResumeExtractionError, ProfileError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return resume_payload(workspace.workspace_id, profile.profile_id)

    @app.get(
        "/v1/resumes/{profile_id}",
        response_model=ResumeResponse,
        dependencies=[Depends(require_token)],
    )
    def review_resume(profile_id: str, workspace_id: str) -> ResumeResponse:
        try:
            return resume_payload(workspace_id, profile_id)
        except ProfileNotFoundError as error:
            raise HTTPException(status_code=404, detail="resume not found") from error

    @app.post(
        "/v1/resumes/{profile_id}/confirm",
        response_model=ResumeStateResponse,
        dependencies=[Depends(require_token)],
    )
    def confirm_resume(
        profile_id: str, request: ResumeConfirmationRequest
    ) -> ResumeStateResponse:
        try:
            core.profiles.confirm_profile(
                workspace_id=request.workspace_id,
                profile_id=profile_id,
                accepted_fact_ids=request.accepted_fact_ids,
                corrections=request.corrections,
            )
        except (ProfileError, ProfileNotFoundError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return resume_state(request.workspace_id)

    @app.post(
        "/v1/resumes/{profile_id}/abandon",
        response_model=ResumeStateResponse,
        dependencies=[Depends(require_token)],
    )
    def abandon_resume(profile_id: str, workspace_id: str) -> ResumeStateResponse:
        try:
            core.profiles.abandon_active_draft(
                workspace_id=workspace_id,
                profile_id=profile_id,
            )
        except ProfileNotFoundError as error:
            raise HTTPException(
                status_code=404, detail="active draft not found"
            ) from error
        return resume_state(workspace_id)

    @app.post(
        "/v1/resumes/analysis-preview",
        response_model=AnalysisPreviewResponse,
        dependencies=[Depends(require_token)],
    )
    def analysis_preview(
        request: AnalysisPreviewRequest,
    ) -> AnalysisPreviewResponse:
        current = core.profiles.current_version(workspace_id=request.workspace_id)
        if current is None:
            raise HTTPException(status_code=409, detail="no confirmed resume version")
        text = "\n".join(
            f"{section}:\n" + "\n".join(values)
            for section, values in current.content.items()
            if values
        )
        if request.privacy_mode not in {"redact", "keep"}:
            raise HTTPException(status_code=400, detail="invalid privacy mode")
        fields = (
            set()
            if request.privacy_mode == "keep"
            else None
            if request.redacted_fields is None
            else set(request.redacted_fields)
        )
        try:
            copy = create_analysis_copy(
                source_version_id=current.version_id,
                text=text,
                redacted_fields=fields,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return AnalysisPreviewResponse(
            source_version_id=copy.source_version_id,
            redacted_fields=list(copy.redacted_fields),
            text=copy.text,
            limitations=copy.limitations,
        )

    @app.get(
        "/v1/resume-versions",
        response_model=list[ResumeVersionResponse],
        dependencies=[Depends(require_token)],
    )
    def list_resume_versions(workspace_id: str) -> list[ResumeVersionResponse]:
        return [
            _resume_version_payload(version)
            for version in core.resume_editor.list_versions(workspace_id=workspace_id)
        ]

    @app.delete(
        "/v1/resume-versions/{version_id}",
        dependencies=[Depends(require_token)],
    )
    def hide_resume_version(version_id: str, workspace_id: str) -> dict:
        try:
            core.resume_editor.hide_version(
                workspace_id=workspace_id, version_id=version_id
            )
        except ResumeEditorError as error:
            code = (
                409
                if "current" in str(error)
                else 404
            )
            raise HTTPException(status_code=code, detail=str(error)) from error
        return {"hidden": True}

    @app.post(
        "/v1/resume-versions",
        response_model=ResumeVersionResponse,
        dependencies=[Depends(require_token)],
    )
    def edit_resume(request: ResumeEditRequest) -> ResumeVersionResponse:
        try:
            version = core.resume_editor.save_edit(
                workspace_id=request.workspace_id,
                base_version_id=request.base_version_id,
                content=request.content,
            )
        except ResumeEditorError as error:
            code = 409 if "conflict" in str(error) else 400
            raise HTTPException(status_code=code, detail=str(error)) from error
        return _resume_version_payload(version)

    @app.post(
        "/v1/resume-versions/{version_id}/restore",
        response_model=ResumeVersionResponse,
        dependencies=[Depends(require_token)],
    )
    def restore_resume(
        version_id: str, request: ResumeRestoreRequest
    ) -> ResumeVersionResponse:
        try:
            version = core.resume_editor.restore_version(
                workspace_id=request.workspace_id, version_id=version_id
            )
        except ResumeEditorError as error:
            code = 409 if "conflict" in str(error) else 400
            raise HTTPException(status_code=code, detail=str(error)) from error
        return _resume_version_payload(version)

    @app.post(
        "/v1/resume-versions/{version_id}/export",
        response_model=ResumeExportResponse,
        dependencies=[Depends(require_token)],
    )
    def export_resume(
        version_id: str, request: ResumeExportRequest
    ) -> ResumeExportResponse:
        try:
            exported = core.resume_editor.export(
                workspace_id=request.workspace_id,
                version_id=version_id,
                destination=request.destination,
                format=request.format,
                template=request.template,
            )
        except (OSError, ResumeEditorError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return ResumeExportResponse(
            path=str(exported.path),
            format=exported.format,
            template=exported.template,
            version_id=exported.version_id,
        )

    @app.post(
        "/v1/resume-edit-sessions",
        response_model=PromptSessionResponse,
        dependencies=[Depends(require_token)],
    )
    def create_resume_edit_session(
        request: PromptSessionRequest,
    ) -> PromptSessionResponse:
        try:
            connection = model_connections.get(request.connection_id)
            session = prompt_editor.create_session(
                workspace_id=request.workspace_id,
                base_version_id=request.base_version_id,
                connection=connection,
                target_title=request.target_title,
                target_url=request.target_url,
                target_jd=request.target_jd,
            )
        except LookupError as error:
            raise HTTPException(
                status_code=404, detail="connection not found"
            ) from error
        except PromptResumeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _prompt_session_payload(session)

    @app.get(
        "/v1/resume-edit-sessions",
        response_model=list[PromptSessionResponse],
        dependencies=[Depends(require_token)],
    )
    def list_resume_edit_sessions(workspace_id: str) -> list[PromptSessionResponse]:
        return [
            _prompt_session_payload(session)
            for session in prompt_editor.list_sessions(workspace_id=workspace_id)
        ]

    @app.get(
        "/v1/resume-edit-sessions/{session_id}",
        response_model=PromptSessionResponse,
        dependencies=[Depends(require_token)],
    )
    def get_resume_edit_session(session_id: str) -> PromptSessionResponse:
        try:
            return _prompt_session_payload(prompt_editor.get_session(session_id))
        except PromptResumeError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post(
        "/v1/resume-edit-sessions/{session_id}/turns",
        response_model=PromptSessionResponse,
        dependencies=[Depends(require_token)],
    )
    def generate_resume_edit_turn(
        session_id: str, request: PromptTurnRequest
    ) -> PromptSessionResponse:
        cancellation = CancellationToken()
        try:
            session = prompt_editor.get_session(session_id)
            connection = model_connections.get(session.connection_id)
            with active_prompt_requests_lock:
                if any(
                    active[0] == session_id
                    for active in active_prompt_requests.values()
                ):
                    raise PromptResumeError(
                        "a turn is already running in this conversation"
                    )
                if request.request_id in active_prompt_requests:
                    raise PromptResumeError("prompt request id is already active")
                active_prompt_requests[request.request_id] = (
                    session_id,
                    cancellation,
                )
            generated = prompt_editor.generate_turn(
                session_id=session_id,
                connection=connection,
                api_key=request.api_key,
                user_prompt=request.prompt,
                project_facts=request.project_facts,
                optional_jd=request.optional_jd,
                redacted_fields=(
                    None
                    if request.redacted_fields is None
                    else set(request.redacted_fields)
                ),
                cancellation=cancellation,
            )
        except LookupError as error:
            raise HTTPException(
                status_code=404, detail="connection not found"
            ) from error
        except ModelCancelledError as error:
            raise HTTPException(
                status_code=409, detail="resume edit cancelled"
            ) from error
        except (ModelGatewayError, PromptResumeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        finally:
            with active_prompt_requests_lock:
                active = active_prompt_requests.get(request.request_id)
                if active is not None and active[1] is cancellation:
                    active_prompt_requests.pop(request.request_id, None)
        return _prompt_session_payload(generated)

    @app.post(
        "/v1/resume-edit-sessions/{session_id}/requests/{request_id}/cancel",
        response_model=PromptSessionResponse,
        dependencies=[Depends(require_token)],
    )
    def cancel_resume_edit_turn(
        session_id: str, request_id: str
    ) -> PromptSessionResponse:
        with active_prompt_requests_lock:
            active = active_prompt_requests.get(request_id)
            if active is not None and active[0] == session_id:
                active[1].cancel()
        try:
            return _prompt_session_payload(prompt_editor.get_session(session_id))
        except PromptResumeError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post(
        "/v1/resume-edit-sessions/{session_id}/patches/{patch_id}",
        response_model=PromptSessionResponse,
        dependencies=[Depends(require_token)],
    )
    def decide_resume_patch(
        session_id: str, patch_id: str, request: PatchDecisionRequest
    ) -> PromptSessionResponse:
        try:
            session = prompt_editor.decide_patch(
                session_id=session_id,
                patch_id=patch_id,
                decision=request.decision,
            )
        except PromptResumeError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _prompt_session_payload(session)

    @app.post(
        "/v1/resume-edit-sessions/{session_id}/save",
        response_model=ResumeVersionResponse,
        dependencies=[Depends(require_token)],
    )
    def save_resume_edit_session(session_id: str) -> ResumeVersionResponse:
        try:
            return _resume_version_payload(
                prompt_editor.save_as_version(session_id=session_id)
            )
        except PromptResumeError as error:
            code = 409 if "conflict" in str(error) else 400
            raise HTTPException(status_code=code, detail=str(error)) from error

    @app.get(
        "/v1/model-connections",
        response_model=list[ModelConnectionResponse],
        dependencies=[Depends(require_token)],
    )
    def list_model_connections() -> list[ModelConnectionResponse]:
        return [_model_payload(item) for item in model_connections.list()]

    @app.post(
        "/v1/model-connections",
        response_model=ModelConnectionResponse,
        dependencies=[Depends(require_token)],
    )
    def save_model_connection(
        request: ModelConnectionRequest,
    ) -> ModelConnectionResponse:
        try:
            connection = model_connections.save(**request.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _model_payload(connection)

    @app.post(
        "/v1/model-connections/{connection_id}/test",
        response_model=ModelConnectionResponse,
        dependencies=[Depends(require_token)],
    )
    def test_model_connection(
        connection_id: str, request: ModelTestRequest
    ) -> ModelConnectionResponse:
        cancellation = CancellationToken()
        try:
            connection = model_connections.get(connection_id)
            with active_model_tests_lock:
                for active_test_id, (active_connection_id, token) in tuple(
                    active_model_tests.items()
                ):
                    if active_connection_id == connection_id:
                        token.cancel()
                        active_model_tests.pop(active_test_id, None)
                active_model_tests[request.test_id] = (connection_id, cancellation)
                model_connections.begin_test(
                    connection_id=connection_id,
                    test_id=request.test_id,
                )
            result = model_gateway.generate_structured(
                connection=connection,
                api_key=request.api_key,
                prompt="Reply with OK.",
                timeout_seconds=request.timeout_seconds,
                cancellation=cancellation,
            )
            tested = model_connections.finish_test(
                connection_id=connection_id,
                test_id=request.test_id,
                status=ConnectionStatus.VERIFIED,
                usage=result.usage,
            )
        except LookupError as error:
            raise HTTPException(
                status_code=404, detail="connection not found"
            ) from error
        except ModelCancelledError:
            tested = model_connections.finish_test(
                connection_id=connection_id,
                test_id=request.test_id,
                status=ConnectionStatus.CANCELLED,
                error="connection test cancelled",
            )
        except ModelGatewayError as error:
            tested = model_connections.finish_test(
                connection_id=connection_id,
                test_id=request.test_id,
                status=ConnectionStatus.FAILED,
                error=str(error),
            )
        finally:
            with active_model_tests_lock:
                active = active_model_tests.get(request.test_id)
                if active is not None and active[1] is cancellation:
                    active_model_tests.pop(request.test_id, None)
        return _model_payload(tested)

    @app.post(
        "/v1/model-connections/{connection_id}/tests/{test_id}/cancel",
        response_model=ModelConnectionResponse,
        dependencies=[Depends(require_token)],
    )
    def cancel_model_connection_test(
        connection_id: str, test_id: str
    ) -> ModelConnectionResponse:
        try:
            with active_model_tests_lock:
                active = active_model_tests.get(test_id)
                if active is not None and active[0] == connection_id:
                    active[1].cancel()
            cancelled = model_connections.cancel_test(
                connection_id=connection_id,
                test_id=test_id,
            )
        except LookupError as error:
            raise HTTPException(
                status_code=404, detail="connection not found"
            ) from error
        return _model_payload(cancelled)

    @app.post(
        "/v1/research-jobs",
        response_model=dict,
        dependencies=[Depends(require_token)],
    )
    def prepare_research_job(request: ResearchJobRequest) -> dict:
        from jobfindsme.research.job_input import prepare_job

        try:
            return prepare_job(research.jobs, **request.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/v1/jobs/{job_id}/source-detail", dependencies=[Depends(require_token)])
    def enrich_source_detail(job_id: str, request: BossDetailRequest) -> dict:
        from jobfindsme.research.job_input import enrich_source_job

        try:
            return enrich_source_job(
                research.jobs, job_id=job_id, **request.model_dump(mode="json")
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail="job not found") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/v1/jobs/{job_id}/boss-detail", dependencies=[Depends(require_token)])
    def enrich_boss_detail(job_id: str, request: BossDetailRequest) -> dict:
        from jobfindsme.research.job_input import enrich_boss_job

        try:
            return enrich_boss_job(
                research.jobs, job_id=job_id, **request.model_dump(mode="json")
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail="job not found") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post(
        "/v1/research-runs",
        response_model=dict,
        dependencies=[Depends(require_token)],
    )
    def create_research_report(request: ResearchRunRequest) -> dict:
        try:
            report = research.create_report(
                workspace_id=request.workspace_id,
                job_id=request.job_id,
                resume_version_id=request.resume_version_id,
                team=request.team,
                directions=tuple(request.directions),
                topics=tuple(request.topics),
                context_company=request.context_company,
                context_description=request.context_description,
                interest_question=request.interest_question,
                source_ids=tuple(request.source_ids),
                user_evidence=tuple(
                    item.model_dump() for item in request.user_evidence
                ),
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail="job not found") from error
        except ResearchError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if request.connection_id is None:
            if request.api_key or request.request_id:
                raise HTTPException(
                    status_code=400,
                    detail="model credentials require a selected connection",
                )
            return report
        if request.api_key is None or not request.request_id:
            raise HTTPException(
                status_code=400,
                detail="selected model requires request_id and a secure API key",
            )
        try:
            connection = model_connections.get(request.connection_id)
        except LookupError as error:
            raise HTTPException(
                status_code=404, detail="connection not found"
            ) from error
        if connection.status is not ConnectionStatus.VERIFIED:
            raise HTTPException(
                status_code=409, detail="model connection is not verified"
            )
        cancellation = CancellationToken()
        with active_research_requests_lock:
            active_research_requests[request.request_id] = (
                report["report_id"],
                cancellation,
            )
        try:
            result = model_gateway.generate_structured(
                connection=connection,
                api_key=request.api_key,
                prompt=research.model_prompt(
                    workspace_id=request.workspace_id,
                    report_id=report["report_id"],
                ),
                timeout_seconds=45,
                cancellation=cancellation,
            )
            return research.apply_model_result(
                workspace_id=request.workspace_id,
                report_id=report["report_id"],
                connection_id=request.connection_id,
                structured=result.structured,
                status="complete",
            )
        except ModelCancelledError:
            return research.apply_model_result(
                workspace_id=request.workspace_id,
                report_id=report["report_id"],
                connection_id=request.connection_id,
                structured=None,
                status="cancelled",
                error="请求已取消；若服务商已收到请求，仍可能产生用量。",
            )
        except (ModelGatewayError, ResearchError) as error:
            return research.apply_model_result(
                workspace_id=request.workspace_id,
                report_id=report["report_id"],
                connection_id=request.connection_id,
                structured=None,
                status="failed",
                error=str(error),
            )
        finally:
            with active_research_requests_lock:
                active = active_research_requests.get(request.request_id)
                if active is not None and active[1] is cancellation:
                    active_research_requests.pop(request.request_id, None)

    @app.post(
        "/v1/research-requests/{request_id}/cancel",
        response_model=dict,
        dependencies=[Depends(require_token)],
    )
    def cancel_research_report(request_id: str, workspace_id: str) -> dict:
        with active_research_requests_lock:
            active = active_research_requests.get(request_id)
            if active is not None:
                active[1].cancel()
                report_id = active[0]
            else:
                raise HTTPException(
                    status_code=409, detail="research request is not active"
                )
        try:
            return research.get_report(
                workspace_id=workspace_id,
                report_id=report_id,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail="report not found") from error

    @app.post(
        "/v1/research-runs/{report_id}/corrections",
        dependencies=[Depends(require_token)],
    )
    def correct_research(report_id: str, request: ResearchCorrectionRequest) -> dict:
        try:
            return research.correct(report_id=report_id, **request.model_dump())
        except LookupError as error:
            raise HTTPException(status_code=404, detail="evidence not found") from error
        except ResearchError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get(
        "/v1/research-runs",
        response_model=list[dict],
        dependencies=[Depends(require_token)],
    )
    def list_research_reports(workspace_id: str) -> list[dict]:
        return research.list_reports(workspace_id=workspace_id)

    @app.delete(
        "/v1/research-runs/{report_id}",
        dependencies=[Depends(require_token)],
    )
    def hide_research_report(report_id: str, workspace_id: str) -> dict:
        try:
            research.hide_report(workspace_id=workspace_id, report_id=report_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail="report not found") from error
        return {"hidden": True}

    @app.post(
        "/v1/tasks",
        response_model=dict,
        dependencies=[Depends(require_token)],
    )
    def create_scheduled_task(request: ScheduledTaskRequest) -> dict:
        raise HTTPException(status_code=410, detail="定时检索已停用；请使用手动岗位检索。")

    @app.get(
        "/v1/tasks",
        response_model=list[dict],
        dependencies=[Depends(require_token)],
    )
    def list_scheduled_tasks(workspace_id: str) -> list[dict]:
        return scheduler.list_tasks(workspace_id=workspace_id)

    @app.get(
        "/v1/tasks/due",
        response_model=list[dict],
        dependencies=[Depends(require_token)],
    )
    def list_due_tasks() -> list[dict]:
        return []

    @app.post(
        "/v1/tasks/{task_id}/pause",
        response_model=dict,
        dependencies=[Depends(require_token)],
    )
    def pause_scheduled_task(task_id: str) -> dict:
        try:
            return scheduler.set_paused(task_id=task_id, paused=True)
        except LookupError as error:
            raise HTTPException(status_code=404, detail="task not found") from error

    @app.post(
        "/v1/tasks/{task_id}/resume",
        response_model=dict,
        dependencies=[Depends(require_token)],
    )
    def resume_scheduled_task(task_id: str) -> dict:
        raise HTTPException(status_code=410, detail="定时检索已停用；历史计划不能恢复。")

    @app.post(
        "/v1/tasks/run-due",
        response_model=dict,
        dependencies=[Depends(require_token)],
    )
    def run_due_tasks(request: RunDueTasksRequest) -> dict:
        return {"runs": [], "notifications": []}

    @app.post(
        "/v1/task-notifications/{notification_id}/delivered",
        response_model=dict,
        dependencies=[Depends(require_token)],
    )
    def deliver_task_notification(notification_id: str) -> dict:
        try:
            scheduler.mark_notification_delivered(notification_id)
        except LookupError as error:
            raise HTTPException(
                status_code=404, detail="notification not found"
            ) from error
        return {"notification_id": notification_id, "delivered": True}

    @app.get(
        "/v1/tasks/legacy-status",
        response_model=dict,
        dependencies=[Depends(require_token)],
    )
    def legacy_task_status(workspace_id: str) -> dict:
        return scheduler.legacy_status(workspace_id=workspace_id)

    return app


def _resume_capabilities() -> ResumeCapabilities:
    return ResumeCapabilities(
        supported_formats=["PDF", "DOCX", "MD", "TXT"],
        doc_status="unsupported",
        ocr_status="unavailable",
        detail="旧 DOC 需先转换为 DOCX；扫描 PDF 暂无 OCR，需换用文字版文件。",
    )


def _preflight_payload(preflight) -> SearchPreflightResponse:
    return SearchPreflightResponse(
        workspace_id=preflight.workspace_id,
        resume_version_id=preflight.resume_version_id,
        keywords=list(preflight.keywords),
        allowed_source_ids=list(preflight.allowed_source_ids),
        blocked_sources=preflight.blocked_sources,
        max_pages=preflight.max_pages,
        time_budget_seconds=preflight.time_budget_seconds,
    )


def _resume_version_payload(version) -> ResumeVersionResponse:
    return ResumeVersionResponse(
        version_id=version.version_id,
        parent_version_id=version.parent_version_id,
        version_number=version.version_number,
        content={key: list(values) for key, values in version.content.items()},
        is_current=version.is_current,
        created_at=version.created_at.isoformat(),
    )


def _prompt_session_payload(session) -> PromptSessionResponse:
    return PromptSessionResponse(
        session_id=session.session_id,
        workspace_id=session.workspace_id,
        base_version_id=session.base_version_id,
        connection_id=session.connection_id,
        status=session.status,
        messages=list(session.messages),
        target_title=session.target_title,
        target_url=session.target_url,
        target_jd=session.target_jd,
        saved_version_id=session.saved_version_id,
        patches=[
            PromptPatchResponse(
                patch_id=patch.patch_id,
                turn_number=patch.turn_number,
                section=patch.section,
                before=list(patch.before),
                after=list(patch.after),
                rationale=patch.rationale,
                evidence_ids=list(patch.evidence_ids),
                needs_user_input=list(patch.needs_user_input),
                status=patch.status,
            )
            for patch in session.patches
        ],
    )


def _model_payload(connection) -> ModelConnectionResponse:
    return ModelConnectionResponse(
        connection_id=connection.connection_id,
        provider=connection.provider,
        protocol=connection.protocol.value,
        endpoint=connection.endpoint,
        model_id=connection.model_id,
        status=connection.status.value,
        last_error=connection.last_error,
        last_tested_at=connection.last_tested_at.isoformat()
        if connection.last_tested_at
        else None,
        input_tokens=connection.input_tokens,
        output_tokens=connection.output_tokens,
        credential_ref=connection.credential_ref,
        auth_mode=connection.auth_mode,
    )
