# DESIGN — agent-witness

## What it is

A small library that reconciles an AI agent's narrated output against its own structured
tool-execution audit trail, and flags claims the record does not support. v1 catches the
concrete, evidenced case: a JSON-shaped tool-call envelope in the narration with no matching
executed record.

## Why standalone, not part of agent-guard

agent-guard and agent-witness sit on opposite sides of the tool-dispatch boundary, in
different temporal phases:

```
                         tool-dispatch boundary
                                  |
   agent decides to act  ->  [ agent-guard ]  ->  tool runs  ->  [ agent-witness ]
                            allow / deny /          (or is         diff narration
                            require_human           blocked)       vs. the record
                            BEFORE dispatch,                       AFTER, off an
                            in real time                           existing record
```

- **Different phase.** agent-guard is a gate: it must run inline, before dispatch, and its
  decision changes what happens next. agent-witness is a reconciler: it runs after the fact,
  reads a record that already exists, and changes nothing about the execution.
- **Different consumer.** A guard is consumed by the agent runtime at the dispatch seam. A
  reconciler is consumed by a reviewer, a CI gate, an eval harness, or an observability
  pipeline looking back at a completed turn.
- **Different failure mode.** A guard fails dangerously if it lets a forbidden action through.
  A reconciler fails dangerously if it says "all clear" on a turn that actually diverged — so
  its correctness bar is *fail closed on anything it cannot verify*, a different discipline
  from a policy engine's first-match evaluation.

Bolting reconciliation onto the guard would couple an after-the-fact analysis to the hot,
inline authorization path and force a hard dependency on one audit format. Keeping it separate
lets the diff engine work against any structured record source. agent-guard's `AuditRecord` is
the **first reference adapter it consumes**, exactly the same design discipline agent-guard and
agent-warrant already follow (wrap a plain shape, depend on no one harness).

## Core shape

```
ExecutionRecord  { tool: str, args: dict, executed: bool }   # minimal internal ground truth
ClaimedAction    { tool: str, args: dict, raw: str }         # what the narration claimed
Divergence       { kind, tool, detail, claim }               # a finding
check(narration, records) -> list[Divergence]
```

The internal `ExecutionRecord` is deliberately narrower than agent-guard's `AuditRecord`
(which also carries `ts`, `agent_id`, `decision`, `reason`, `rule_id`, `sig`, `error`). Only
`tool`/`args`/`executed` are load-bearing for reconciliation, so a future adapter for a
different audit format (an MCP call log, a bespoke trail) maps three fields, not ten, and
never needs agent-guard installed.

## Detection strategy (v1): JSON-shaped claims only

One detection strategy, chosen because it is the real evidenced failure and it is cheap and
deterministic. The engine scans narration text for balanced `{...}` spans (respecting string
literals so braces inside JSON strings do not miscount), parses each, and treats an object as
a tool-call claim when it names a tool and carries invocation marks (`type: function`, or a
`parameters`/`arguments` payload). A plain data object like `{"name": "Alice", "age": 30}`
matches none of these and is not flagged.

Free-text claim extraction ("I ran X") is explicitly **v2**, not silently unhandled — a
prose-only narration yields zero claims, and the docs say so plainly rather than implying full
coverage.

## Prior art and the validated gap

The concept is not novel to this project, and the docs credit that honestly. A March 2026
arXiv paper, *"Tool Receipts, Not Zero-Knowledge Proofs"* (arXiv:2603.10060), proposes almost
exactly this: compare agent narration against structured execution logs and flag
discrepancies. It is a research paper — no shipped implementation was found.

A scan of the curated `systempromptio/awesome-ai-agent-governance` list confirmed no existing
OSS tool does this reconciliation specifically. There is extensive adjacent tooling — audit,
policy, and observability layers (e.g. Bifrost, Asqav, Provenrail) — but none diff narration
against execution. So the gap this fills is real and, as of this writing, unbuilt in OSS. The
contribution here is a small, working, harness-agnostic implementation of a concept the
research already validated, not a claim to have invented it.

## Non-goals

- Explaining *why* a model hallucinated (this reports that it did).
- Detecting silent actions (executed record, no narration mention) in v1 — a reliable detector
  needs the same free-text matching v1 defers; documented non-goal.
- Verifying the audit source itself. The record is trusted as ground truth, the same posture
  agent-guard's own audit trail takes. See THREAT_MODEL.md.
