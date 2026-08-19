from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from .witness import ExecutionRecord


class AuditRecordLike(Protocol):
    tool: str
    args: dict[str, Any]
    executed: bool


def from_audit_records(records: Iterable[AuditRecordLike]) -> list[ExecutionRecord]:
    """Adapt agent-guard's `AuditRecord` shape (as held by a `MemoryAuditSink.records`
    list) into this engine's `ExecutionRecord`.

    Duck-typed on `.tool`/`.args`/`.executed` on purpose: agent-guard is the first
    reference source, not a dependency, so this never imports it."""
    return [
        ExecutionRecord(tool=record.tool, args=dict(record.args), executed=bool(record.executed)) for record in records
    ]


def from_jsonl(path: str | Path) -> list[ExecutionRecord]:
    """Adapt an agent-guard `JsonlAuditSink` file into `ExecutionRecord`s.

    Fails closed: a malformed line, a non-object line, or a record missing its `tool` or
    boolean `executed` field raises — an unreadable audit trail must surface loudly, never
    degrade into a short record list that makes real claims look falsely unverified (or
    silent actions invisible)."""
    path = Path(path)
    records: list[ExecutionRecord] = []
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            records.append(_record_from_line(stripped, path, lineno))
    return records


def _record_from_line(line: str, path: Path, lineno: int) -> ExecutionRecord:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as err:
        raise ValueError(f"malformed audit record on line {lineno} of {path}: {err}") from err

    if not isinstance(payload, dict):
        raise ValueError(f"audit record on line {lineno} of {path} is not a JSON object")

    tool = payload.get("tool")
    if not isinstance(tool, str) or not tool:
        raise ValueError(f"audit record on line {lineno} of {path} has no non-empty 'tool' field")

    executed = payload.get("executed")
    if not isinstance(executed, bool):
        raise ValueError(f"audit record on line {lineno} of {path} has no boolean 'executed' field")

    args = payload.get("args")
    if not isinstance(args, dict):
        args = {}

    return ExecutionRecord(tool=tool, args=args, executed=executed)
