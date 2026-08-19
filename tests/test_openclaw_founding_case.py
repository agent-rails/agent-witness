"""The founding evidence for this project, as a first-class test.

Root-caused in homelab/DECISIONS.md ("Tool-narration bug root-caused"): `llama3.1:8b` via
Ollama, asked only to "Reply with exactly: ok", emitted a raw JSON tool-call envelope as its
ENTIRE visible reply while dispatching zero real tool calls (`toolSummary` absent from the
response envelope). OpenClaw's own tool-call-repair grammar didn't recognize the bare,
unprefixed shape, so nothing was ever promoted to a real call. The narration claimed an
action; the execution record shows none. That is exactly the divergence agent-witness exists
to catch.

The narration strings below are the exact envelopes captured in DECISIONS.md, not simplified
stand-ins."""

from __future__ import annotations

from agent_witness import DivergenceKind, check

OPENCLAW_MINIMAL_NARRATION = '{ "type": "function", "name": "exec", "parameters": {"command": "/approve", "ask": "ok"}}'

OPENCLAW_SECOND_TURN_NARRATION = (
    '{"type": "function", "name": "write", "parameters": '
    '{"path": "MEMORY.md", "content": "[User: Mon 2023-01-29 11:30 GMT.]..."}}'
)

OPENCLAW_FENCED_NARRATION = '```\n{"name": "exec", "parameters": {"cmd": ["node", "run.js"]}}\n```'


def test_founding_case_bare_json_envelope_with_no_execution_is_flagged():
    divergences = check(OPENCLAW_MINIMAL_NARRATION, records=[])

    assert len(divergences) == 1
    divergence = divergences[0]
    assert divergence.kind is DivergenceKind.UNVERIFIED_CLAIM
    assert divergence.tool == "exec"
    assert divergence.claim is not None
    assert divergence.claim.args == {"command": "/approve", "ask": "ok"}


def test_founding_case_second_turn_write_envelope_is_flagged():
    divergences = check(OPENCLAW_SECOND_TURN_NARRATION, records=[])

    assert len(divergences) == 1
    assert divergences[0].tool == "write"
    assert divergences[0].kind is DivergenceKind.UNVERIFIED_CLAIM


def test_founding_case_markdown_fenced_envelope_is_flagged():
    divergences = check(OPENCLAW_FENCED_NARRATION, records=[])

    assert len(divergences) == 1
    assert divergences[0].tool == "exec"
    assert divergences[0].kind is DivergenceKind.UNVERIFIED_CLAIM
