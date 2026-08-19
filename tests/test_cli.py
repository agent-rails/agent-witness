from __future__ import annotations

from agent_witness.cli import main


def _write_audit(tmp_path, line='{"tool":"exec","args":{},"executed":true}\n'):
    path = tmp_path / "audit.jsonl"
    path.write_text(line, encoding="utf-8")
    return path


def test_clean_narration_exits_zero(tmp_path, capsys):
    audit = _write_audit(tmp_path)
    narration = tmp_path / "n.txt"
    narration.write_text('{"name":"exec","parameters":{}}', encoding="utf-8")
    code = main(["check", "--audit", str(audit), "--narration-file", str(narration)])
    assert code == 0


def test_divergent_narration_exits_three(tmp_path, capsys):
    audit = _write_audit(tmp_path)
    narration = tmp_path / "n.txt"
    narration.write_text('{"name":"write","parameters":{}}', encoding="utf-8")
    code = main(["check", "--audit", str(audit), "--narration-file", str(narration)])
    assert code == 3


def test_missing_narration_file_reports_controlled_error_not_traceback(tmp_path, capsys):
    audit = _write_audit(tmp_path)
    missing = tmp_path / "does-not-exist.txt"
    code = main(["check", "--audit", str(audit), "--narration-file", str(missing)])
    captured = capsys.readouterr()
    assert code == 1
    assert "cannot read narration" in captured.err
    assert "Traceback" not in captured.err


def test_missing_audit_file_reports_controlled_error(tmp_path, capsys):
    missing = tmp_path / "no-audit.jsonl"
    narration = tmp_path / "n.txt"
    narration.write_text('{"name":"exec","parameters":{}}', encoding="utf-8")
    code = main(["check", "--audit", str(missing), "--narration-file", str(narration)])
    captured = capsys.readouterr()
    assert code == 1
    assert "cannot read audit trail" in captured.err


def test_oversized_narration_fails_closed_via_cli_limit(tmp_path, capsys):
    audit = _write_audit(tmp_path)
    narration = tmp_path / "n.txt"
    narration.write_text('{"name":"exec","parameters":{}}' + "x" * 100, encoding="utf-8")
    code = main(
        [
            "check",
            "--audit",
            str(audit),
            "--narration-file",
            str(narration),
            "--max-narration-chars",
            "10",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert code == 3
    assert "unverifiable" in captured.out
