from dwim.agent.plan import parse_plan
from dwim.agent.plan_render import render_plan

RAW = '{"steps": [{"kind":"edit","path":"a.py","diff":"+x","why":"guard"},{"kind":"run","command":"pytest -q","why":"verify"}]}'

def test_render_lists_numbered_steps():
    out = render_plan(parse_plan(RAW))
    assert "1." in out and "2." in out
    assert "a.py" in out and "pytest -q" in out
    assert "edit" in out and "run" in out

def test_render_never_raises_on_missing_fields():
    from dwim.agent.plan import Plan
    render_plan(Plan([{"kind": "edit", "path": "x", "why": ""}]))  # no diff
    render_plan(Plan([]))  # empty
