from __future__ import annotations

import pytest

from agent_witness import ScanLimits, extract_claims
from agent_witness.claims import NarrationTooComplexError


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


def test_envelope_nested_in_wrapper_object_is_extracted():
    claims = extract_claims('{"wrapper":{"type":"function","name":"exec","parameters":{"command":"ls"}}}')
    assert len(claims) == 1
    assert claims[0].tool == "exec"
    assert claims[0].args == {"command": "ls"}


def test_envelope_nested_in_array_is_extracted():
    claims = extract_claims('{"items":[{"name":"exec","arguments":{"command":"ls"}}]}')
    assert len(claims) == 1
    assert claims[0].tool == "exec"
    assert claims[0].args == {"command": "ls"}


def test_unterminated_quote_before_envelope_does_not_hide_it():
    claims = extract_claims('prose " never closed {"name":"exec","parameters":{}}')
    assert len(claims) == 1
    assert claims[0].tool == "exec"


def test_stray_open_brace_before_envelope_does_not_hide_it():
    claims = extract_claims('prose { then {"name":"exec","parameters":{}}')
    assert len(claims) == 1
    assert claims[0].tool == "exec"


def test_stray_close_brace_before_envelope_does_not_hide_it():
    claims = extract_claims('prose } then {"name":"exec","parameters":{}}')
    assert len(claims) == 1
    assert claims[0].tool == "exec"


def test_envelope_a_few_levels_deep_is_still_extracted():
    claims = extract_claims('{"a":{"b":{"c":{"name":"exec","parameters":{"command":"ls"}}}}}')
    assert len(claims) == 1
    assert claims[0].tool == "exec"


def test_deeply_nested_input_fails_closed_not_a_crash():
    depth = 500
    narration = '{"x":' * depth + "0" + "}" * depth
    with pytest.raises(NarrationTooComplexError):
        extract_claims(narration)


def test_c_decoder_recursion_error_is_translated_to_fail_closed():
    depth = 50_000
    narration = '{"x":' * depth + "0" + "}" * depth
    with pytest.raises(NarrationTooComplexError):
        extract_claims(narration, ScanLimits(max_depth=depth + 1))


def test_oversized_narration_fails_closed():
    limits = ScanLimits(max_narration_chars=100)
    with pytest.raises(NarrationTooComplexError):
        extract_claims("x" * 101, limits)


def test_two_sequential_envelopes_are_both_extracted():
    claims = extract_claims('{"name":"exec","parameters":{"command":"a"}} {"name":"exec","parameters":{"command":"b"}}')
    assert len(claims) == 2
