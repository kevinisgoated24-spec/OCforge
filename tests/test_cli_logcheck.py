"""`ocforge logcheck` CLI wiring: --log file, stdin fallback, exit codes."""

import json

from ocforge.cli import build_parser, main


def test_logcheck_parser_wiring():
    args = build_parser().parse_args(["logcheck", "--log", "boot.txt"])
    assert args.log == "boot.txt"
    assert args.func.__name__ == "cmd_logcheck"


def test_logcheck_clean_log_exits_zero(tmp_path, capsys):
    log = tmp_path / "boot.txt"
    log.write_text("everything is fine\nnothing to see here\n")
    code = main(["logcheck", "--log", str(log)])
    assert code == 0
    assert "No known trouble signatures" in capsys.readouterr().out


def test_logcheck_finds_issue_exits_one(tmp_path, capsys):
    log = tmp_path / "boot.txt"
    log.write_text("no vault provided!\n")
    code = main(["logcheck", "--log", str(log)])
    assert code == 1
    out = capsys.readouterr().out
    assert "No vault provided" in out
    assert "fix:" in out


def test_logcheck_missing_file_exits_two(capsys):
    code = main(["logcheck", "--log", "/no/such/file.txt"])
    assert code == 2
    assert "not found" in capsys.readouterr().err


def test_logcheck_json_clean(tmp_path, capsys):
    log = tmp_path / "boot.txt"
    log.write_text("everything is fine\n")
    code = main(["logcheck", "--log", str(log), "--json"])
    assert code == 0
    assert json.loads(capsys.readouterr().out) == []


def test_logcheck_json_findings_shape(tmp_path, capsys):
    log = tmp_path / "boot.txt"
    log.write_text("no vault provided!\n")
    code = main(["logcheck", "--log", str(log), "--json"])
    assert code == 1
    findings = json.loads(capsys.readouterr().out)
    assert len(findings) == 1
    assert findings[0].keys() == {"title", "explanation", "suggestion", "line_no", "line"}
    assert findings[0]["title"] == "No vault provided"
