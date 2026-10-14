"""Resume routes: original files, immutable versions and redacted analysis copies."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from jobfindsme.app import jobfindsmecore
from jobfindsme.privacy import create_analysis_copy
from jobfindsme.profiles.models import FactType
from jobfindsme.profiles.parser import ResumeExtractionError
from jobfindsme.profiles.service import ProfileError, ProfileNotFoundError
from jobfindsme.resume_editor import ResumeEditorError
from jobfindsme.search.preparation import JobPreparationService

from .schemas.common import WorkspaceRequest
from .schemas.resumes import (
    AnalysisPreviewRequest,
    AnalysisPreviewResponse,
    ResumeCapabilities,
    ResumeConfirmationRequest,
    ResumeEditRequest,
    ResumeExportRequest,
    ResumeExportResponse,
    ResumeFactResponse,
    ResumeImportRequest,
    ResumeResponse,
    ResumeRestoreRequest,
    ResumeStateResponse,
    ResumeVersionResponse,
)


def create_resume_router(
    *,
    core: jobfindsmecore,
    require_token: Callable[..., None],
    resolve_workspace: Callable,
) -> APIRouter:
    router = APIRouter()

    def resume_review_value(fact) -> str:
        # Older drafts could lose the year when "2020." was read as a list marker.
        if fact.fact_type is FactType.EDUCATION:
            original = " ".join(fact.evidence_snippet.split())
            if (
                re.match(r"^\d{4}\.", original)
                and original.endswith(fact.value)
                and len(original) - len(fact.value) == 5
            ):
                return original
        return fact.value

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
                    value=resume_review_value(fact),
                    status=fact.status.value,
                )
                for fact in profile.facts
            ],
        )

    @router.get(
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
            search_profile_state="ready" if current else "no_resume",
            search_block_reason=None,
            active_draft=active_draft,
            capabilities=_resume_capabilities(),
        )

    @router.post("/v1/resumes/clear-current", dependencies=[Depends(require_token)])
    def clear_current_resume(request: WorkspaceRequest) -> ResumeStateResponse:
        try:
            resolve_workspace(request.workspace_id)
        except LookupError as error:
            raise HTTPException(
                status_code=404, detail="workspace not found"
            ) from error
        core.profiles.clear_current(workspace_id=request.workspace_id)
        return resume_state(request.workspace_id)

    @router.post(
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
                index_original=request.index_original,
            )
        except (OSError, ResumeExtractionError, ProfileError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return resume_payload(workspace.workspace_id, profile.profile_id)

    @router.get("/v1/resumes/source/file", dependencies=[Depends(require_token)])
    def resume_source(workspace_id: str, document_id: str):
        try:
            document, content = core.profiles.original_document(
                workspace_id=workspace_id, document_id=document_id
            )
            text = ""
            if document.media_type != "application/pdf":
                text = core.profiles.extractor.extract(
                    file_name=document.file_name, content=content, allow_empty=True
                ).text
            return {
                "file_name": document.file_name,
                "media_type": document.media_type,
                "content_base64": base64.b64encode(content).decode("ascii"),
                "text": text,
            }
        except (
            OSError,
            ProfileError,
            ProfileNotFoundError,
            ResumeExtractionError,
        ) as error:
            raise HTTPException(
                status_code=404, detail="原文件无法读取，请重新导入"
            ) from error

    @router.post(
        "/v1/resumes/{profile_id}/use-original", dependencies=[Depends(require_token)]
    )
    def use_original_resume(profile_id: str, workspace_id: str):
        try:
            core.profiles.use_original(workspace_id=workspace_id, profile_id=profile_id)
        except (OSError, ProfileError, ProfileNotFoundError) as error:
            raise HTTPException(
                status_code=400, detail="原文件无法使用，请重新导入"
            ) from error
        return resume_state(workspace_id)

    @router.get(
        "/v1/resumes/{profile_id}",
        response_model=ResumeResponse,
        dependencies=[Depends(require_token)],
    )
    def review_resume(profile_id: str, workspace_id: str) -> ResumeResponse:
        try:
            return resume_payload(workspace_id, profile_id)
        except ProfileNotFoundError as error:
            raise HTTPException(status_code=404, detail="resume not found") from error

    @router.post(
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

    @router.post(
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

    @router.post(
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

    @router.get(
        "/v1/resume-versions",
        response_model=list[ResumeVersionResponse],
        dependencies=[Depends(require_token)],
    )
    def list_resume_versions(workspace_id: str) -> list[ResumeVersionResponse]:
        return [
            _resume_version_payload(version)
            for version in core.resume_editor.list_versions(workspace_id=workspace_id)
        ]

    @router.get(
        "/v1/resume-versions/{version_id}",
        response_model=ResumeVersionResponse,
        dependencies=[Depends(require_token)],
    )
    def get_resume_version(version_id: str, workspace_id: str) -> ResumeVersionResponse:
        try:
            return _resume_version_payload(
                core.resume_editor.get_version(
                    workspace_id=workspace_id, version_id=version_id
                )
            )
        except ResumeEditorError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.delete(
        "/v1/resume-versions/{version_id}",
        dependencies=[Depends(require_token)],
    )
    def hide_resume_version(version_id: str, workspace_id: str) -> dict:
        try:
            core.resume_editor.hide_version(
                workspace_id=workspace_id, version_id=version_id
            )
        except ResumeEditorError as error:
            code = 409 if "current" in str(error) else 404
            raise HTTPException(status_code=code, detail=str(error)) from error
        return {"hidden": True}

    @router.post(
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
                document=request.document,
            )
        except ResumeEditorError as error:
            code = 409 if "conflict" in str(error) else 400
            raise HTTPException(status_code=code, detail=str(error)) from error
        return _resume_version_payload(version)

    @router.post(
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

    @router.post(
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

    @router.get("/v1/research-agent/resume", dependencies=[Depends(require_token)])
    def agent_resume(
        workspace_id: str,
        job_id: str | None = None,
        resume_version_id: str | None = None,
    ) -> dict:
        from jobfindsme.privacy import create_analysis_copy
        from jobfindsme.resume_editor.prompt import _evidence_map

        current = None
        if resume_version_id:
            try:
                current = core.resume_editor.get_version(
                    workspace_id=workspace_id, version_id=resume_version_id
                )
            except ValueError as error:
                raise HTTPException(
                    status_code=404, detail="resume not found"
                ) from error
        elif job_id:
            try:
                chosen, version_id = JobPreparationService(
                    core.database
                ).resume_selection(workspace_id, job_id)
                if version_id:
                    current = core.resume_editor.get_version(
                        workspace_id=workspace_id, version_id=version_id
                    )
                elif chosen:
                    raise HTTPException(
                        status_code=409, detail="no resume selected for job"
                    )
            except LookupError as error:
                raise HTTPException(status_code=404, detail="job not found") from error
            except ValueError as error:
                raise HTTPException(
                    status_code=404, detail="resume not found"
                ) from error
        if current is None:
            current = core.profiles.current_version(workspace_id=workspace_id)
        if current is None:
            raise HTTPException(status_code=409, detail="no confirmed resume")
        content = {
            key: [
                create_analysis_copy(
                    source_version_id=current.version_id, text=value
                ).text
                for value in values
            ]
            for key, values in current.content.items()
            if key != "basic_information"
        }
        return {
            "source_version_id": current.version_id,
            "content": content,
            "evidence_ids": list(
                _evidence_map(current, [], include_basic_information=False)
            ),
            "text": json.dumps(content, ensure_ascii=False),
            "limitations": (
                "本机自动提取并脱敏的简历，可能有识别误差；不代表用户逐项确认。"
                if current.original_file
                else "本机保存并脱敏的简历。"
            )
            + "只能提出修改，不会自动保存。",
        }

    return router


def _resume_capabilities() -> ResumeCapabilities:
    return ResumeCapabilities(
        supported_formats=["PDF", "DOCX", "MD", "TXT"],
        doc_status="unsupported",
        ocr_status="unavailable",
        detail="旧 DOC 需先转换为 DOCX；扫描 PDF 可保留和下载原件，暂无 OCR。",
    )


def _resume_version_payload(version) -> ResumeVersionResponse:
    return ResumeVersionResponse(
        source_document_id=version.source_document_id,
        original_file=version.original_file,
        version_id=version.version_id,
        parent_version_id=version.parent_version_id,
        version_number=version.version_number,
        content={key: list(values) for key, values in version.content.items()},
        document=version.document,
        is_current=version.is_current,
        created_at=version.created_at.isoformat(),
    )
