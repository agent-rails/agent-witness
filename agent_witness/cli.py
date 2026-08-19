from __future__ import annotations

import argparse
import json
import sys

from .adapters import from_jsonl
from .claims import DEFAULT_SCAN_LIMITS, ScanLimits
from .witness import Divergence, DivergenceKind, check


def _read_narration(args: argparse.Namespace) -> str:
    if args.narration_file:
        with open(args.narration_file, encoding="utf-8") as handle:
            return handle.read()
    return sys.stdin.read()


def _check(args: argparse.Namespace) -> int:
    """Reconcile a narration against an agent-guard JSONL audit trail.

    Exit codes: 0 no divergence, 1 usage/read error, 3 divergence(s) found (an
    UNVERIFIABLE narration counts as a divergence — the point is to fail closed)."""
    try:
        records = from_jsonl(args.audit)
    except (OSError, ValueError) as err:
        print(f"cannot read audit trail: {err}", file=sys.stderr)
        return 1

    try:
        narration = _read_narration(args)
    except OSError as err:
        print(f"cannot read narration: {err}", file=sys.stderr)
        return 1

    limits = ScanLimits(max_narration_chars=args.max_narration_chars)
    divergences = check(narration, records, limits)

    if args.json:
        print(json.dumps({"divergences": [_as_dict(d) for d in divergences]}, indent=2))
    else:
        _print_human(divergences)

    return 3 if divergences else 0


def _as_dict(divergence: Divergence) -> dict:
    payload = {"kind": divergence.kind.value, "tool": divergence.tool, "detail": divergence.detail}
    if divergence.claim is not None:
        payload["claim"] = {"tool": divergence.claim.tool, "args": divergence.claim.args, "raw": divergence.claim.raw}
    return payload


def _print_human(divergences: list[Divergence]) -> None:
    if not divergences:
        print("no divergence: every JSON-shaped claim matched an executed record")
        return
    print(f"{len(divergences)} divergence(s):")
    for divergence in divergences:
        marker = "!!" if divergence.kind is DivergenceKind.UNVERIFIABLE else "??"
        print(f"  [{marker} {divergence.kind.value}] {divergence.detail}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="witness",
        description="Detect when an agent's narration diverges from its structured execution audit trail.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    check_cmd = sub.add_parser(
        "check",
        help="reconcile a narration against an agent-guard JSONL audit trail",
    )
    check_cmd.add_argument("--audit", required=True, help="path to an agent-guard JsonlAuditSink file")
    check_cmd.add_argument(
        "--narration-file",
        help="file holding the agent's narration text; if omitted, read narration from stdin",
    )
    check_cmd.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    check_cmd.add_argument(
        "--max-narration-chars",
        type=int,
        default=DEFAULT_SCAN_LIMITS.max_narration_chars,
        help="reject narration longer than this many characters (fails closed as unverifiable)",
    )
    check_cmd.set_defaults(func=_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
