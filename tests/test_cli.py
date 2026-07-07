import subprocess, sys, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(args, extra_env=None):
    env = dict(os.environ, PYTHONPATH=REPO)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "dwim", *args],
        capture_output=True, text=True, env=env,
    )


def test_cli_prints_suggestion():
    r = _run(["--cmd", "brw install pip", "--exit", "127"],
             extra_env={"DWIM_FAKE_SUGGESTION": "brew install pip"})
    assert r.returncode == 0
    assert r.stdout.strip() == "brew install pip"


def test_cli_no_suggestion_exit_1():
    r = _run(["--cmd", "ls", "--exit", "0"],
             extra_env={"DWIM_FAKE_SUGGESTION": ""})
    assert r.returncode == 1
    assert r.stdout.strip() == ""


def test_refresh_inventory_cli(tmp_path, monkeypatch):
    from dwim import context, __main__ as m
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(context, "_DOCS", str(tmp_path / "Documents"))

    class _Res:
        stdout = "1.0G\t" + str(tmp_path / "Documents/foo") + "\n"
    monkeypatch.setattr(context.subprocess, "run", lambda *a, **k: _Res())
    assert m.main(["--refresh-inventory"]) == 0
    assert (tmp_path / "dwim" / "inventory").exists()


def test_action_tier_deep_uses_deep_model(monkeypatch):
    from dwim import __main__ as m
    seen = {}

    def fake_run_action(intent, *, runner, context, model="haiku"):
        seen["model"] = model
        return {"answer": "", "commands": []}

    monkeypatch.setattr("dwim.action.run_action", fake_run_action)
    monkeypatch.setattr("dwim.context.gather", lambda: {"cwd": "/c"})
    monkeypatch.setattr("dwim.claude_runner.run", lambda *a, **k: "")
    m.main(["--action", "why is x big", "--tier", "deep"])
    assert seen["model"] == "sonnet"


def test_action_default_tier_uses_fast_model(monkeypatch):
    from dwim import __main__ as m
    seen = {}

    def fake_run_action(intent, *, runner, context, model="haiku"):
        seen["model"] = model
        return {"answer": "", "commands": []}

    monkeypatch.setattr("dwim.action.run_action", fake_run_action)
    monkeypatch.setattr("dwim.context.gather", lambda: {"cwd": "/c"})
    monkeypatch.setattr("dwim.claude_runner.run", lambda *a, **k: "")
    m.main(["--action", "how do I zip a folder"])
    assert seen["model"] == "haiku"
