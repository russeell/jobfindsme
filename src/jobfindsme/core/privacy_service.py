"""Privacy use case — local data portability and two-phase deletion.

Export writes a local file and returns only its path/hash/counts;
deletion always runs preview → confirm with a short-lived token.
"""

from __future__ import annotations

from typing import Any

from jobfindsme.context import ActiveContextService
from jobfindsme.privacy import DeletionPreview, DeletionResult, PrivacyService


class PrivacyUseCase:
    def __init__(
        self,
        *,
        context: ActiveContextService,
        privacy: PrivacyService,
    ) -> None:
        self.context = context
        self.privacy = privacy

    def export_local_data(self, workspace_id: str) -> dict[str, Any]:
        return self.privacy.export_workspace(workspace_id)

    def export_local_file(self, workspace_id: str | None = None):
        workspace = self.context.resolve_workspace(workspace_id)
        return self.privacy.export_workspace_to_file(workspace.workspace_id)

    def preview_delete(
        self,
        *,
        workspace_id: str | None = None,
        scope: str,
    ) -> DeletionPreview:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.privacy.preview_delete(
            workspace_id=workspace.workspace_id,
            scope=scope,
        )

    def confirm_delete(
        self,
        *,
        workspace_id: str | None = None,
        scope: str,
        confirmation_token: str,
    ) -> DeletionResult:
        workspace = self.context.resolve_workspace(workspace_id)
        return self.privacy.confirm_delete(
            workspace_id=workspace.workspace_id,
            scope=scope,
            confirmation_token=confirmation_token,
        )
