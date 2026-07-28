from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import Field

from jobfindsme.contracts import SourceKind, StrictModel


class ConnectorPolicy(StrictModel):
    """Explicit permission boundary for every remote source."""

    public_access: bool
    robots_allowed: bool
    authorized: bool = False

    @property
    def can_fetch(self) -> bool:
        return self.public_access and self.robots_allowed or self.authorized


class RawJobRecord(StrictModel):
    source_kind: SourceKind
    source_name: str = Field(min_length=1)
    source_url: str
    external_id: str = Field(min_length=1)
    payload: Mapping[str, Any]


class Connector(Protocol):
    def fetch(self) -> list[RawJobRecord]: ...
