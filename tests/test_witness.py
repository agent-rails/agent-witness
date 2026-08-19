from __future__ import annotations

from agent_witness import DivergenceKind, ExecutionRecord, check


def executed(tool: str, **args) -> ExecutionRecord:
    return ExecutionRecord(tool=tool, args=args, executed=True)


def blocked(tool: str, **args) -> ExecutionRecord:
    return ExecutionRecord(tool=tool, args=args, executed=False)


def test_claim_matching_an_executed_record_is_not_flagged():
    narration = '{"type": "function", "name": "exec", "parameters": {"command": "ls"}}'
    divergences = check(narration, records=[executed("exec", command="ls")])
    assert divergences == []


def test_multiple_claims_partial_match_flags_only_the_unmatched():
    narration = (
        'first: {"name": "read", "parameters": {"path": "a.txt"}} '
        'then: {"name": "exec", "parameters": {"command": "rm -rf /"}}'
    )
    divergences = check(narration, records=[executed("read", path="a.txt")])

    assert len(divergences) == 1
    assert divergences[0].tool == "exec"
    assert divergences[0].kind is DivergenceKind.UNVERIFIED_CLAIM


def test_claim_matching_only_a_blocked_record_is_still_flagged():
    narration = '{"name": "exec", "parameters": {"command": "rm -rf /"}}'
    divergences = check(narration, records=[blocked("exec", command="rm -rf /")])

    assert len(divergences) == 1
    assert divergences[0].tool == "exec"


def test_prose_narration_with_no_json_claim_and_empty_records_is_clean():
    divergences = check("I looked at the file and it seemed fine.", records=[])
    assert divergences == []


def test_empty_narration_fails_closed_as_unverifiable():
    divergences = check("", records=[executed("exec", command="ls")])
    assert len(divergences) == 1
    assert divergences[0].kind is DivergenceKind.UNVERIFIABLE


def test_whitespace_only_narration_fails_closed_as_unverifiable():
    divergences = check("   \n\t ", records=[])
    assert len(divergences) == 1
    assert divergences[0].kind is DivergenceKind.UNVERIFIABLE


def test_non_string_narration_fails_closed_as_unverifiable():
    divergences = check(None, records=[])  # type: ignore[arg-type]
    assert len(divergences) == 1
    assert divergences[0].kind is DivergenceKind.UNVERIFIABLE


def test_plain_data_object_in_narration_is_not_a_tool_claim():
    narration = 'user profile: {"name": "Alice", "age": 30}'
    divergences = check(narration, records=[])
    assert divergences == []


def test_duplicate_claims_both_flag_when_unmatched():
    narration = '{"name": "exec", "parameters": {"command": "a"}} {"name": "exec", "parameters": {"command": "b"}}'
    divergences = check(narration, records=[])
    assert len(divergences) == 2
