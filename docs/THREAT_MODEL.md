# THREAT_MODEL — agent-witness

Naming the boundary honestly is as much the deliverable as the code. This states what
agent-witness defends, and — critically — what it does not.

## What it is for

Catching a specific, evidenced failure: an agent narrates a tool action that its own
structured execution record does not support. The concrete founding case is a small local
model emitting a JSON tool-call envelope as its visible reply while zero real tool calls were
dispatched (see the `agent-rails/homelab` `DECISIONS.md` root-cause). This is an *integrity of
narration* check, run after the fact, off an existing record.

## Trust boundary

```
   [ model narration ]        [ execution audit trail ]
     UNTRUSTED free text        TRUSTED ground truth
            \                        /
             \                      /
              v                    v
              agent-witness.check(...)
              -> list[Divergence]  (advisory; changes nothing about execution)
```

- The **narration** is the untrusted input. It is arbitrary model output; the engine parses it
  defensively and never executes anything from it.
- The **execution record** is trusted as ground truth. agent-witness diffs against it; it does
  not and cannot independently confirm that the record itself is complete or honest.
- The output is **advisory**. This is a post-hoc reconciler, not a gate — it does not block,
  approve, or alter any action. Acting on a divergence (fail a CI run, alert a reviewer, quarantine
  a turn) is the caller's decision.

## What it defends against

- A narrated JSON tool-call claim with no matching executed record — the founding case.
- A narrated claim that matches only a *blocked* record (`executed == False`): "I ran X" when X
  was denied is still flagged.
- Silent failure on unusable input: an empty or non-text narration returns a single
  `unverifiable` divergence, never an empty "all clear". A malformed or incomplete audit line
  (via `from_jsonl`) raises rather than degrading into a short record list that would make real
  claims look falsely unverified.

## What it explicitly does NOT protect against

- **Free-text claims.** v1 extracts only JSON-shaped envelopes. "I ran the tests and they
  passed", with no JSON, produces no claim. A model that narrates purely in prose evades v1.
  Stated v2 gap, not silent.
- **Silent actions.** An executed record the narration never mentions is not flagged in v1
  (documented non-goal — a reliable detector needs the free-text matching v1 defers).
- **A lying or compromised audit source.** The record is ground truth here. A producer that
  fabricates records, or suppresses them, defeats this tool — the same limit agent-guard's own
  `SigningAuditSink` documents: signing defends a record *after* it leaves the producer, not
  against a compromised producer, and does not detect a record that was simply never written.
  agent-witness inherits that boundary and does not try to re-solve it.
- **Explaining the hallucination.** It reports *that* narration and execution diverged, not
  *why* the model did it.
- **Args-level fidelity.** v1 matches a claim to a record by tool name and execution status,
  not by argument equality. A claim naming a tool that did execute is treated as verified even
  if the narrated args differ from what ran. Argument-level reconciliation is deferred.
- **Unbounded resource exhaustion.** Narration is untrusted, so the scanner bounds every
  dimension a hostile author could inflate — total size, candidate count, nesting depth, node
  count — via `ScanLimits` (configurable by library callers, `--max-narration-chars` on the
  CLI). Exceeding a limit fails closed as `UNVERIFIABLE`, never a silent empty result or an
  escaping crash. What it does not promise is a tuned ceiling for every deployment: the
  defaults are sane, not calibrated to your host — a caller feeding multi-megabyte narration
  should set its own limits.

## Positioning against standards

The relevant risk is OWASP Agentic ASI06-class *excessive agency / misreported action* and the
underlying LLM-layer hallucination: an agent representing an action as done when it was not.
agent-witness is a detective control for that class after the fact — it composes with a
preventive control (a policy gate such as agent-guard) rather than replacing it. It makes no
identity or authorization claims; it reads a record and reports a discrepancy.
