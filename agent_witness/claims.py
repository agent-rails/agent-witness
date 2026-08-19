from __future__ import annotations

import json
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


def extract_claims(narration: str) -> list[ClaimedAction]:
    """Extract JSON-shaped tool-call claims from an agent's narration text.

    v1 detects only the structural, machine-shaped case: a JSON object embedded anywhere
    in the text (whole-string, markdown-fenced, or inline) that looks like a tool-call
    envelope. This is the exact shape of the OpenClaw tool-narration bug that founded this
    project — a small local model emitting `{"type":"function","name":...,"parameters":...}`
    as its visible reply while dispatching zero real tool calls.

    Free-text claims ("I ran X", "I wrote to Y") are a stated v2 gap, not silently handled —
    see docs/THREAT_MODEL.md. Returning an empty list here means "no JSON-shaped claim was
    found", never "the narration is safe"."""
    claims: list[ClaimedAction] = []
    for obj in _find_json_objects(narration):
        if _looks_like_tool_call(obj):
            claims.append(
                ClaimedAction(
                    tool=obj["name"],
                    args=_extract_args(obj),
                    raw=json.dumps(obj, sort_keys=True, separators=(",", ":")),
                )
            )
    return claims


def _find_json_objects(text: str) -> list[dict[str, Any]]:
    """Scan text for top-level balanced `{...}` spans and return those that parse as JSON
    objects. Tracks string literals so braces inside JSON strings never miscount depth."""
    objects: list[dict[str, Any]] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
            continue
        if char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start != -1:
                candidate = text[start : index + 1]
                parsed = _try_parse_object(candidate)
                if parsed is not None:
                    objects.append(parsed)
                start = -1

    return objects


def _try_parse_object(candidate: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


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
