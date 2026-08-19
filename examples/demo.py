"""Run the founding OpenClaw case end-to-end against a real agent-guard audit trail.

Builds a real `MemoryAuditSink`, records what actually executed (nothing, for the buggy
turn), then reconciles the model's narrated JSON envelope against it. Doubles as a CI
smoke test: exits non-zero if the known divergence is not caught."""

from __future__ import annotations

from agent_guard import AuditRecord, MemoryAuditSink

from agent_witness import DivergenceKind, check, from_audit_records

OPENCLAW_NARRATION = '{ "type": "function", "name": "exec", "parameters": {"command": "/approve", "ask": "ok"}}'


def main() -> int:
    sink = MemoryAuditSink()
    sink.write(
        AuditRecord(
            ts="2026-08-19T00:00:00+00:00",
            agent_id="openclaw:main",
            tool="web_search",
            args={"query": "local model fit"},
            decision="allow",
            reason="allowed",
            rule_id=None,
            executed=True,
        )
    )

    divergences = check(OPENCLAW_NARRATION, from_audit_records(sink.records))

    print("narration claimed a tool call; audit trail shows only:")
    for record in sink.records:
        print(f"  executed={record.executed} tool={record.tool}")

    print(f"\ndivergences: {len(divergences)}")
    for divergence in divergences:
        print(f"  [{divergence.kind.value}] {divergence.detail}")

    assert len(divergences) == 1
    assert divergences[0].kind is DivergenceKind.UNVERIFIED_CLAIM
    assert divergences[0].tool == "exec"
    print("\nOK: the fabricated 'exec' claim was caught against the real audit trail.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
