from dwim.agent.planner import make_plan, PLAN_SYSTEM

def fake_runner_valid(prompt, model, **kw):
    return ('{"steps":[{"kind":"edit","path":"a.py","diff":"+x","why":"g"},'
            '{"kind":"run","command":"pytest -q","why":"v"}]}', "sess1")

def fake_runner_garbage(prompt, model, **kw):
    return ("I could not form a plan.", "sess2")

def test_make_plan_parses_runner_output():
    p = make_plan("fix it", "claude-sonnet-5", 600, runner=fake_runner_valid)
    assert p is not None and p.files() == {"a.py"}

def test_make_plan_returns_none_on_garbage():
    assert make_plan("fix it", "claude-sonnet-5", 600, runner=fake_runner_garbage) is None

def test_plan_prompt_demands_json_and_readonly():
    assert "json" in PLAN_SYSTEM.lower()
    assert "do not" in PLAN_SYSTEM.lower() or "read-only" in PLAN_SYSTEM.lower()
