import json
from dwim.agent.confine_hook import run_hook

PLAN = {"files": ["dwim/rag/search.py"], "commands": ["pytest -q"]}
ROOT = "/repo"

def decision(tool, inp):
    stdin = json.dumps({"tool_name": tool, "tool_input": inp})
    out = json.loads(run_hook(stdin, PLAN, ROOT))
    return out["hookSpecificOutput"]["permissionDecision"]

def test_allows_approved_edit():
    assert decision("Edit", {"file_path": "/repo/dwim/rag/search.py"}) == "allow"

def test_denies_offplan_edit():
    assert decision("Edit", {"file_path": "/repo/dwim/x.py"}) == "deny"

def test_denies_hard_denylist():
    assert decision("Bash", {"command": "git push"}) == "deny"

def test_malformed_stdin_denies_closed():
    out = json.loads(run_hook("not json", PLAN, ROOT))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
