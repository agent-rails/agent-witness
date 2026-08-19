from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .claims import ClaimedAction, extract_claims


class DivergenceKind(Enum):
    UNVERIFIED_CLAIM = "unverified_claim"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True)
class ExecutionRecord:
    """The minimal internal ground-truth shape this engine diffs against: what tool ran,
    with what args, and whether it actually executed. Deliberately narrower than any one
    audit format so no single audit source (agent-guard's `AuditRecord`, an MCP log, a
    bespoke trail) is a hard dependency — adapters map into this."""

    tool: str
    args: dict[str, Any]
    executed: bool


@dataclass(frozen=True)
class Divergence:
    kind: DivergenceKind
    tool: str | None
    detail: str
    claim: ClaimedAction | None = None


def check(narration: str, records: Sequence[ExecutionRecord]) -> list[Divergence]:
    """Diff what an agent *said* it did against what its execution record *shows* it did.

    Returns one `Divergence` per unmatched claim. An empty list means every JSON-shaped
    claim in the narration matched an executed record — it does NOT mean the narration is
    unconditionally honest (free-text claims are not extracted in v1).

    Fails closed on unusable narration: a `None`, non-string, or empty/whitespace-only
    narration cannot be verified, so it returns a single `UNVERIFIABLE` divergence rather
    than an empty list that a caller could misread as 'all clear'."""
    if not isinstance(narration, str) or not narration.strip():
        return [
            Divergence(
                kind=DivergenceKind.UNVERIFIABLE,
                tool=None,
                detail="narration is empty or not text; cannot verify claims against the execution record",
            )
        ]

    executed_tools = {record.tool for record in records if record.executed}

    divergences: list[Divergence] = []
    for claim in extract_claims(narration):
        if claim.tool not in executed_tools:
            divergences.append(
                Divergence(
                    kind=DivergenceKind.UNVERIFIED_CLAIM,
                    tool=claim.tool,
                    detail=(
                        f"narration claims tool '{claim.tool}' ran, "
                        "but no executed record in the audit trail matches it"
                    ),
                    claim=claim,
                )
            )
    return divergences
