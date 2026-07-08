import json
import os
import subprocess
from dwim.agent.plan import parse_plan
from dwim.agent import execute as execmod
from dwim.agent.execute import write_approved_plan, snapshot, execute, _default_runner

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
    def fake_runner(prompt, plan_file, repo_root, cfg):
        calls["plan_file"] = plan_file
        calls["prompt"] = prompt
        # read the plan during the run — execute() unlinks it after the runner returns
        calls["plan_data"] = json.loads(open(plan_file).read())
        return ("done: 1 file changed, tests green", "sess9")
    def fake_snap(root, **kw):
        return "cafe"
    out = execute(PLAN, str(tmp_path), {"model": "claude-sonnet-5", "max_iterations": 12, "timeout": 600},
                  task="make the failing test pass",
                  runner=fake_runner, snapshotter=fake_snap)
    assert out["snapshot"] == "cafe" and out["session"] == "sess9"
    assert "green" in out["report"]
    # the plan file the hook reads was written and passed to the runner
    assert calls["plan_data"]["files"] == ["a.py"]
    # the runner prompt carries the original task + a planned command
    captured_prompt = calls["prompt"]
    assert "make the failing test pass" in captured_prompt
    assert "pytest" in captured_prompt


def test_default_runner_timeout_returns_report_not_raises(tmp_path, monkeypatch):
    plan_file = tmp_path / "plan.json"
    write_approved_plan(PLAN, str(plan_file))

    def raising_run(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1, output="")

    monkeypatch.setattr(execmod.subprocess, "run", raising_run)
    cfg = {"model": "claude-sonnet-5", "max_iterations": 12, "timeout": 1}
    text, session = _default_runner("p", str(plan_file), str(tmp_path), cfg)
    assert "timed out" in text
    assert not session


def test_execute_unlinks_plan_file_after_run(tmp_path):
    seen = {}
    def fake_runner(prompt, plan_file, repo_root, cfg):
        seen["plan_file"] = plan_file
        # the hook needs it during the run
        assert os.path.exists(plan_file)
        return ("done", "sess1")
    def fake_snap(root, **kw):
        return "cafe"
    execute(PLAN, str(tmp_path), {"model": "m", "max_iterations": 1, "timeout": 1},
            task="t", runner=fake_runner, snapshotter=fake_snap)
    assert not os.path.exists(seen["plan_file"])
