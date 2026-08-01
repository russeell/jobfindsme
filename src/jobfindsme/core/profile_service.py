"""Profile use case — the user-facing "Profile" concept (我是谁).

Owns resume import/review/confirm and profile-derived plan suggestions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from jobfindsme.context import ActiveContextService
from jobfindsme.contracts import SuggestedPlan
from jobfindsme.plan_suggestions import suggest_search_plan
from jobfindsme.profiles.models import (
    CandidateProfile,
    ProfileSummary,
    ResumeImportMode,
)
from jobfindsme.profiles.service import ResumeProfileService


class ProfileUseCase:
    def __init__(
        self,
        *,
        context: ActiveContextService,
        profiles: ResumeProfileService,
    ) -> None:
        self.context = context
        self.profiles = profiles

    def import_resume(
        self,
        *,
        workspace_id: str | None = None,
        source_path: str | Path,
        mode: ResumeImportMode = ResumeImportMode.FORGET_SOURCE,
    ) -> CandidateProfile:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.profiles.import_resume(
            workspace_id=workspace.workspace_id,
            source_path=source_path,
            mode=mode,
        )

    def confirm_profile(
        self,
        *,
        workspace_id: str | None = None,
        profile_id: str,
        accepted_fact_ids: Sequence[str],
        corrections: Mapping[str, str] | None = None,
    ) -> ProfileSummary:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.profiles.confirm_profile(
            workspace_id=workspace.workspace_id,
            profile_id=profile_id,
            accepted_fact_ids=accepted_fact_ids,
            corrections=corrections,
        )

    def review_profile(
        self,
        *,
        profile_id: str,
        workspace_id: str | None = None,
    ) -> CandidateProfile:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.profiles.load_review(
            workspace_id=workspace.workspace_id,
            profile_id=profile_id,
        )

    def suggest_plan(self, *, workspace_id: str | None = None) -> SuggestedPlan:
        workspace = self.context.resolve_workspace(workspace_id)
        summary = self.profiles.latest_confirmed_summary(
            workspace_id=workspace.workspace_id
        )
        return suggest_search_plan(summary)
