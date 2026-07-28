from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from typing import Any

from jobfindsme.connectors.base import RawJobRecord
from jobfindsme.contracts import SourceKind


def _records(
    rows: list[Mapping[str, Any]],
    *,
    kind: SourceKind,
    source_name: str,
    source_url: str,
) -> list[RawJobRecord]:
    result = []
    for index, row in enumerate(rows):
        external_id = row.get("external_id") or row.get("id") or row.get("url") or index
        result.append(
            RawJobRecord(
                source_kind=kind,
                source_name=source_name,
                source_url=source_url,
                external_id=str(external_id),
                payload=dict(row),
            )
        )
    return result


def parse_csv(
    content: str, *, source_name: str, source_url: str = "local://csv"
) -> list[RawJobRecord]:
    rows = list(csv.DictReader(io.StringIO(content)))
    return _records(
        rows,
        kind=SourceKind.CSV,
        source_name=source_name,
        source_url=source_url,
    )


def parse_json(
    content: str, *, source_name: str, source_url: str = "local://json"
) -> list[RawJobRecord]:
    value = json.loads(content)
    rows = value.get("jobs", []) if isinstance(value, dict) else value
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("JSON import must contain an array of job objects")
    return _records(
        rows,
        kind=SourceKind.JSON,
        source_name=source_name,
        source_url=source_url,
    )
