# agent-witness

[![ci](https://github.com/agent-rails/agent-witness/actions/workflows/ci.yml/badge.svg)](https://github.com/agent-rails/agent-witness/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.13%2B-3776ab.svg)](pyproject.toml)

Detect when an AI agent's narrated output diverges from what its own structured
tool-execution audit trail actually shows happened. One small library that diffs what the
model *said* it did against what the record *shows* it did, and flags the gaps.

Harness-agnostic by design: the core engine works against a plain list of execution records
(`{tool, args, executed}`), which any audit source can map into. agent-guard's `AuditRecord`
is the first reference adapter, not a required dependency.

## The problem

A model can narrate an action it never took. The founding evidence for this project
(root-caused in the `agent-rails/homelab` `DECISIONS.md`): `llama3.1:8b` via Ollama, asked
only to "Reply with exactly: ok", emitted a raw JSON tool-call envelope as its **entire
visible reply** while dispatching **zero** real tool calls —

```json
{ "type": "function", "name": "exec", "parameters": {"command": "/approve", "ask": "ok"}}
```

The harness's own tool-call-repair grammar didn't recognize the bare, unprefixed shape, so
nothing was ever promoted to a real call. The turn *looked* like it did something; the audit
trail for it is empty. That divergence — a claim with no matching execution record — is
exactly what agent-witness catches.

This is a distinct phase from authorization. A policy gate (agent-guard's job) decides
`allow`/`deny`/`require_human` *before* dispatch, in real time. Reconciliation happens
*after*, off an existing record. Different phase, different consumer, different failure mode —
so it's a separate library (see [`docs/DESIGN.md`](docs/DESIGN.md)).

## Install

```bash
pip install agent-witness
```

From source (dev — pulls in agent-guard for the real-adapter tests):

```bash
git clone https://github.com/agent-rails/agent-witness && cd agent-witness
pip install -e ".[dev]" && python -m pytest -q
```

## Use — Python API

```python
from agent_witness import check, ExecutionRecord

narration = '{ "type": "function", "name": "exec", "parameters": {"command": "/approve"}}'
records = []  # the audit trail for this turn is empty — nothing dispatched

for divergence in check(narration, records):
    print(divergence.kind.value, divergence.tool, "-", divergence.detail)
# unverified_claim exec - narration claims tool 'exec' ran, but no executed record matches it
```

Against a real agent-guard audit trail:

```python
from agent_guard import MemoryAuditSink
from agent_witness import check, from_audit_records

sink = MemoryAuditSink()  # your Guard writes AuditRecords here as it runs
# ... agent turn runs ...
divergences = check(agent_final_message, from_audit_records(sink.records))
```

## Use — CLI

```bash
witness check --audit audit.jsonl --narration-file reply.txt
# or pipe the narration on stdin:
echo '{"name":"exec","parameters":{"command":"ls"}}' | witness check --audit audit.jsonl
```

Exit codes: `0` no divergence, `3` divergence(s) found, `1` usage/read error.

## How it works

1. Extract JSON-shaped tool-call claims from the narration text (whole-string, markdown-fenced,
   or inline). An envelope counts as a claim when it names a tool and carries invocation marks
   (`type: function`, or a `parameters`/`arguments` payload).
2. Build the set of tools that actually executed (`executed == True`) from the record list.
3. Flag every claim whose tool has no matching executed record as `unverified_claim`.
4. Fail closed: an empty or non-text narration returns a single `unverifiable` divergence, never
   an empty "all clear".

A claim that matches only a *blocked* record (`executed == False`) is still flagged — "I ran X"
when X was denied is a real divergence.

## What this does NOT do (v1)

- **Free-text claims** ("I ran the tests", "I wrote to config.yaml") are not extracted. v1
  handles the JSON-shaped case, which is the real, evidenced one. Free-text extraction is a
  stated v2 gap, not silently handled — a prose-only narration with no JSON envelope produces
  no claims.
- **Silent actions** (an executed record the narration never mentions) are a documented
  non-goal for v1, because a reliable detector needs the same free-text matching v1 defers.
- **Why** a model hallucinated — this reports *that* narration and execution diverged, not the
  cause.
- **Trust the audit source.** Like agent-guard's own audit trail, this treats the execution
  record as ground truth. A compromised or lying audit source is out of scope. See
  [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — why this is standalone and not bolted onto agent-guard;
  the research that validated the gap.
- [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) — trust boundary, what it defends, and what it
  explicitly does not.
