from dwim.__main__ import main


def test_classify_flag(capsys):
    assert main(["--classify", "fix the bug"]) == 0
    assert capsys.readouterr().out.strip() == "task"
    assert main(["--classify", "how does it work"]) == 0
    assert capsys.readouterr().out.strip() == "question"


def test_confine_hook_flag_denies_offplan(monkeypatch, tmp_path, capsys):
    import json
    pf = tmp_path / "plan.json"
    pf.write_text(json.dumps({"files": ["a.py"], "commands": []}))
    monkeypatch.setenv("DWIM_APPROVED_PLAN", str(pf))
    monkeypatch.setenv("DWIM_REPO_ROOT", "/repo")
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(
        json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "/repo/other.py"}})))
    assert main(["--confine-hook"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
