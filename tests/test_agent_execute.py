import json
from dwim.agent.plan import parse_plan
from dwim.agent.execute import write_approved_plan, snapshot, execute

PLAN = parse_plan('{"steps":[{"kind":"edit","path":"a.py","diff":"+x","why":"g"},{"kind":"run","command":"pytest -q","why":"v"}]}')


def test_write_approved_plan_shape(tmp_path):
    p = tmp_path / "plan.json"
    write_approved_plan(PLAN, str(p))
    data = json.loads(p.read_text())
    assert data["files"] == ["a.py"] and data["commands"] == ["pytest -q"]


def test_snapshot_returns_hash():
    def fake_run(args, **kw):
        class R: stdout = "deadbeef\n"; returncode = 0
        return R()
    assert snapshot("/repo", run=fake_run) == "deadbeef"


def test_snapshot_none_on_failure():
    def fake_run(args, **kw):
        class R: stdout = ""; returncode = 1
        return R()
    assert snapshot("/repo", run=fake_run) is None


def test_execute_calls_runner_and_reports(tmp_path):
    calls = {}
    def fake_runner(plan_file, repo_root, cfg):
        calls["plan_file"] = plan_file
        return ("done: 1 file changed, tests green", "sess9")
    def fake_snap(root, **kw):
        return "cafe"
    out = execute(PLAN, str(tmp_path), {"model": "claude-sonnet-5", "max_iterations": 12, "timeout": 600},
                  runner=fake_runner, snapshotter=fake_snap)
    assert out["snapshot"] == "cafe" and out["session"] == "sess9"
    assert "green" in out["report"]
    # the plan file the hook reads was written and passed to the runner
    assert json.loads(open(calls["plan_file"]).read())["files"] == ["a.py"]
