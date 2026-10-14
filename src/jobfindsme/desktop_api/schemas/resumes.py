from pydantic import Field

from jobfindsme.profiles.models import ResumeImportMode

from .common import StrictResponse


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
    index_original: bool = False


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
    source_document_id: str
    original_file: bool = False
    version_id: str
    parent_version_id: str | None
    version_number: int
    content: dict[str, list[str]]
    document: dict | None = None
    is_current: bool
    created_at: str


class ResumeEditRequest(StrictResponse):
    workspace_id: str
    base_version_id: str
    content: dict[str, list[str]]
    document: dict | None = None


class ResumeRestoreRequest(StrictResponse):
    workspace_id: str


class ResumeExportRequest(StrictResponse):
    workspace_id: str
    destination: str
    format: str
    template: str | None = None


class ResumeExportResponse(StrictResponse):
    path: str
    format: str
    template: str
    version_id: str
