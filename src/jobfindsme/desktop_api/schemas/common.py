from pydantic import BaseModel, ConfigDict


class StrictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkspaceRequest(StrictResponse):
    workspace_id: str
