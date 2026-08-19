from __future__ import annotations

from agent_witness import extract_claims


def test_whole_string_json_envelope_is_extracted():
    claims = extract_claims('{"type": "function", "name": "exec", "parameters": {"command": "ls"}}')
    assert len(claims) == 1
    assert claims[0].tool == "exec"
    assert claims[0].args == {"command": "ls"}


def test_openai_style_arguments_key_is_extracted():
    claims = extract_claims('{"name": "search", "arguments": {"query": "cats"}}')
    assert len(claims) == 1
    assert claims[0].tool == "search"
    assert claims[0].args == {"query": "cats"}


def test_inline_envelope_among_prose_is_extracted():
    claims = extract_claims('Sure, running {"name": "write", "parameters": {"path": "x"}} now.')
    assert len(claims) == 1
    assert claims[0].tool == "write"


def test_plain_data_object_is_not_a_claim():
    claims = extract_claims('{"name": "Alice", "age": 30}')
    assert claims == []


def test_object_named_but_no_invocation_marks_is_not_a_claim():
    claims = extract_claims('{"name": "exec"}')
    assert claims == []


def test_braces_inside_json_strings_do_not_break_scanning():
    claims = extract_claims('{"name": "write", "parameters": {"content": "a } brace { in text"}}')
    assert len(claims) == 1
    assert claims[0].args == {"content": "a } brace { in text"}


def test_no_json_returns_no_claims():
    assert extract_claims("just some plain narration text") == []


def test_type_function_without_parameters_is_still_a_claim():
    claims = extract_claims('{"type": "function", "name": "noop"}')
    assert len(claims) == 1
    assert claims[0].tool == "noop"
    assert claims[0].args == {}
