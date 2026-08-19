"""Adapter tests run against a REAL agent-guard `MemoryAuditSink`/`AuditRecord`, not a
hand-rolled fake, so the adapter is proven against the actual reference shape it claims to
consume. `toolcall-authz` (agent-guard's PyPI distribution) is a dev/test dependency."""

from __future__ import annotations

import json

import pytest

from agent_witness import ExecutionRecord, check, from_audit_records, from_jsonl

agent_guard = pytest.importorskip(
    "agent_guard",
    reason="install the dev extra (`pip install -e '.[dev]'`) to run the agent-guard adapter tests",
)
from agent_guard import AuditRecord, MemoryAuditSink  # noqa: E402


def a_record(tool: str, executed: bool, **args) -> AuditRecord:
    return AuditRecord(
        ts="2026-08-19T00:00:00+00:00",
        agent_id="agent:test",
        tool=tool,
        args=args,
        decision="allow" if executed else "deny",
        reason="test",
        rule_id=None,
        executed=executed,
    )


def test_from_audit_records_adapts_a_real_memory_sink():
    sink = MemoryAuditSink()
    sink.write(a_record("exec", executed=True, command="ls"))
    sink.write(a_record("write", executed=False, path="x"))

    records = from_audit_records(sink.records)

    assert records == [
        ExecutionRecord(tool="exec", args={"command": "ls"}, executed=True),
        ExecutionRecord(tool="write", args={"path": "x"}, executed=False),
    ]


def test_end_to_end_against_a_real_memory_sink_flags_the_unexecuted_claim():
    sink = MemoryAuditSink()
    sink.write(a_record("read", executed=True, path="a.txt"))

    narration = (
        '{"name": "read", "parameters": {"path": "a.txt"}} and {"name": "exec", "parameters": {"command": "rm -rf /"}}'
    )
    divergences = check(narration, from_audit_records(sink.records))

    assert len(divergences) == 1
    assert divergences[0].tool == "exec"


def test_from_jsonl_reads_a_real_jsonl_audit_file(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text(
        json.dumps({"ts": "t", "tool": "exec", "args": {"command": "ls"}, "executed": True}) + "\n",
        encoding="utf-8",
    )
    records = from_jsonl(path)
    assert records == [ExecutionRecord(tool="exec", args={"command": "ls"}, executed=True)]


def test_from_jsonl_skips_blank_lines(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text(
        '\n{"tool": "exec", "args": {}, "executed": true}\n\n',
        encoding="utf-8",
    )
    assert len(from_jsonl(path)) == 1


def test_from_jsonl_fails_closed_on_malformed_line(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"tool": "exec", "args": {}, "executed": true}\nnot json at all\n', encoding="utf-8")
    with pytest.raises(ValueError, match="malformed audit record on line 2"):
        from_jsonl(path)


def test_from_jsonl_fails_closed_on_missing_executed_field(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"tool": "exec", "args": {}}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="boolean 'executed'"):
        from_jsonl(path)


def test_from_jsonl_fails_closed_on_missing_tool_field(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"args": {}, "executed": true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="'tool' field"):
        from_jsonl(path)


def test_from_jsonl_rejects_duplicate_keys(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"tool":"exec","args":{},"executed":false,"executed":true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate key"):
        from_jsonl(path)


def test_from_jsonl_accepts_missing_args_as_empty(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"tool":"exec","executed":true}\n', encoding="utf-8")
    records = from_jsonl(path)
    assert records == [ExecutionRecord(tool="exec", args={}, executed=True)]


def test_from_jsonl_rejects_present_non_object_args(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"tool":"exec","args":"ls","executed":true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="non-object 'args'"):
        from_jsonl(path)
