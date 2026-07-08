from dwim.agent.plan import parse_plan

VALID = '''```json
{"steps": [
  {"kind": "edit", "path": "dwim/rag/search.py", "diff": "+guard", "why": "guard len"},
  {"kind": "run", "command": "pytest tests/test_search.py -q", "why": "verify"},
  {"kind": "run", "command": "git commit -am x", "why": "commit"}
]}
```'''

def test_parse_valid_plan_extracts_files_and_commands():
    p = parse_plan(VALID)
    assert p is not None
    assert p.files() == {"dwim/rag/search.py"}
    assert p.commands() == ["pytest tests/test_search.py -q", "git commit -am x"]
    assert len(p.steps) == 3

def test_parse_malformed_returns_none():
    assert parse_plan("not json at all") is None
    assert parse_plan("") is None
    assert parse_plan('{"steps": []}') is None          # empty plan is useless
    assert parse_plan('{"steps": [{"kind": "bogus"}]}') is None  # no valid step
