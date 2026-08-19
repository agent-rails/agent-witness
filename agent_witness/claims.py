from __future__ import annotations

import json
import unicodedata
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ClaimedAction:
    """A tool call a model *narrated* in its visible output — not (yet) proven to have run.

    `tool` and `args` are what the narration claimed; `raw` is the canonical JSON of the
    envelope that was matched, kept so a divergence report can quote the exact text a
    reviewer would see on screen."""

    tool: str
    args: dict[str, Any]
    raw: str


@dataclass(frozen=True)
class ScanLimits:
    """Explicit ceilings on how much untrusted narration the scanner will process.

    Narration is untrusted input, so every dimension a hostile author could inflate to
    exhaust memory or stack (total size, candidate count, nesting depth, node count) is
    bounded here rather than left to the interpreter's own recursion limit. Library callers
    can pass their own `ScanLimits`; the CLI uses `DEFAULT_SCAN_LIMITS`. Exceeding any limit
    fails closed (`NarrationTooComplexError`), never a silent truncation or an escaping
    crash."""

    max_narration_chars: int = 5_000_000
    max_candidates: int = 100_000
    max_depth: int = 100
    max_nodes: int = 1_000_000


DEFAULT_SCAN_LIMITS = ScanLimits()


class NarrationTooComplexError(ValueError):
    """Raised when narration exceeds a `ScanLimits` ceiling. Callers convert this into a
    fail-closed outcome (an UNVERIFIABLE divergence), never a silent empty result."""


def canonical_tool(name: str) -> str:
    """Canonicalize a tool name for comparison: strip surrounding whitespace and normalize
    Unicode to NFC. Case is preserved — tool names are identifiers, `Exec` and `exec` are
    different tools. Applied at ingestion on both the claim and the record side so visually
    identical names never produce spurious divergences."""
    return unicodedata.normalize("NFC", name.strip())


def extract_claims(narration: str, limits: ScanLimits = DEFAULT_SCAN_LIMITS) -> list[ClaimedAction]:
    """Extract JSON-shaped tool-call claims from an agent's narration text.

    v1 detects the structural, machine-shaped case: a JSON object embedded anywhere in the
    text (whole-string, markdown-fenced, inline) that looks like a tool-call envelope —
    including envelopes nested inside a wrapper object or array. This is the exact shape of
    the OpenClaw tool-narration bug that founded this project — a small local model emitting
    `{"type":"function","name":...,"parameters":...}` as its visible reply while dispatching
    zero real tool calls.

    The scan is restartable: it attempts a decode from every plausible `{` and recovers from
    a malformed candidate, so one stray quote or brace earlier in untrusted narration cannot
    silence every real claim after it.

    Raises `NarrationTooComplexError` when the narration exceeds a `ScanLimits` ceiling.
    Free-text claims ("I ran X") are a stated v2 gap — see docs/THREAT_MODEL.md. An empty
    list means "no JSON-shaped claim was found", never "the narration is safe"."""
    if not isinstance(narration, str):
        return []
    if len(narration) > limits.max_narration_chars:
        raise NarrationTooComplexError(
            f"narration is {len(narration)} chars, exceeds max_narration_chars={limits.max_narration_chars}"
        )

    claims: list[ClaimedAction] = []
    for obj in _iter_candidate_objects(narration, limits):
        for envelope in _walk_for_envelopes(obj, limits):
            claims.append(
                ClaimedAction(
                    tool=canonical_tool(envelope["name"]),
                    args=_extract_args(envelope),
                    raw=json.dumps(envelope, sort_keys=True, separators=(",", ":")),
                )
            )
    return claims


def _iter_candidate_objects(text: str, limits: ScanLimits) -> list[dict[str, Any]]:
    """Scan for JSON objects by attempting a decode from every `{`. On a malformed candidate
    the scan advances one character and retries, so earlier garbage never poisons later
    parsing. On a successful decode the scan jumps past the whole object — nested envelopes
    are found by walking the parsed structure, not by re-scanning inner braces."""
    decoder = json.JSONDecoder()
    candidates: list[dict[str, Any]] = []
    index = 0
    length = len(text)

    while index < length:
        if text[index] != "{":
            index += 1
            continue
        try:
            obj, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            index += 1
            continue
        except RecursionError as err:
            raise NarrationTooComplexError(f"narration nesting exceeds the decoder's limit near char {index}") from err

        if isinstance(obj, dict):
            candidates.append(obj)
            if len(candidates) > limits.max_candidates:
                raise NarrationTooComplexError(
                    f"narration holds more than max_candidates={limits.max_candidates} JSON objects"
                )
            index = end
        else:
            index += 1

    return candidates


def _walk_for_envelopes(root: dict[str, Any], limits: ScanLimits) -> list[dict[str, Any]]:
    """Breadth-first walk of a parsed candidate, returning every envelope-shaped dict within
    it (the candidate itself and any nested inside dict values or array items). Iterative and
    depth/node bounded so a deeply nested structure that decoded in C cannot blow the Python
    stack here — it fails closed instead."""
    found: list[dict[str, Any]] = []
    queue: deque[tuple[Any, int]] = deque([(root, 0)])
    nodes = 0

    while queue:
        value, depth = queue.popleft()
        if depth > limits.max_depth:
            raise NarrationTooComplexError(f"narration nesting exceeds max_depth={limits.max_depth}")
        nodes += 1
        if nodes > limits.max_nodes:
            raise NarrationTooComplexError(f"narration holds more than max_nodes={limits.max_nodes} JSON nodes")

        if isinstance(value, dict):
            if _looks_like_tool_call(value):
                found.append(value)
            for child in value.values():
                if isinstance(child, (dict, list)):
                    queue.append((child, depth + 1))
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, (dict, list)):
                    queue.append((child, depth + 1))

    return found


def _looks_like_tool_call(obj: dict[str, Any]) -> bool:
    """A JSON object is a tool-call claim when it names a tool and carries the marks of an
    invocation envelope: an explicit `type: function`, or a `parameters`/`arguments` payload.
    A plain data object like `{"name": "Alice", "age": 30}` matches none of these."""
    name = obj.get("name")
    if not isinstance(name, str) or not name:
        return False
    if obj.get("type") == "function":
        return True
    return "parameters" in obj or "arguments" in obj


def _extract_args(obj: dict[str, Any]) -> dict[str, Any]:
    for key in ("parameters", "arguments"):
        value = obj.get(key)
        if isinstance(value, dict):
            return value
    return {}
