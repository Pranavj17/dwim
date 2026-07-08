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


def test_run_emits_lossless_cmd_hl():
    # The --run JSON must carry a syntax-highlighted `cmd_hl` for the shell to
    # DISPLAY, and it must strip back byte-for-byte to the raw `cmd`.
    import json
    from dwim.highlight import strip_ansi
    r = _run(["--run", "ls -la"])
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert "cmd_hl" in out
    assert out["cmd"] == "ls -la"
    assert strip_ansi(out["cmd_hl"]) == out["cmd"]
    assert "\033[" in out["cmd_hl"]   # actually colored


def test_run_cmd_hl_present_when_not_run():
    # A mutating command isn't executed here (ran=false) but still gets cmd_hl.
    import json
    from dwim.highlight import strip_ansi
    r = _run(["--run", "rm -rf /tmp/dwim-nonexistent-xyz"])
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["ran"] is False
    assert strip_ansi(out["cmd_hl"]) == out["cmd"]


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


def test_action_passes_resume_and_writes_session_file(tmp_path, monkeypatch):
    from dwim import __main__ as m
    seen = {}

    def fake_run(prompt, model, effort="", resume="", **kw):
        seen["resume"] = resume
        return ("{}", "new-sess")
    monkeypatch.setattr("dwim.claude_runner.run", fake_run)
    monkeypatch.setattr("dwim.context.gather", lambda: {"cwd": "/c"})
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setenv("DWIM_RESUME", "old-sess")
    sess_file = tmp_path / "sess-123"
    monkeypatch.setenv("DWIM_SESSION_FILE", str(sess_file))
    m.main(["--action", "why is x big"])
    assert seen["resume"] == "old-sess"        # inbound resume forwarded
    assert sess_file.read_text() == "new-sess"  # resulting id written per-terminal


def test_action_session_file_defaults_to_cache(tmp_path, monkeypatch):
    from dwim import __main__ as m
    monkeypatch.setattr("dwim.claude_runner.run",
                        lambda prompt, model, effort="", resume="", **kw: ("{}", "sX"))
    monkeypatch.setattr("dwim.context.gather", lambda: {"cwd": "/c"})
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.delenv("DWIM_SESSION_FILE", raising=False)
    monkeypatch.delenv("DWIM_RESUME", raising=False)
    m.main(["--action", "x"])
    assert (tmp_path / "dwim" / "last_session").read_text() == "sX"


def test_action_stamps_last_model(tmp_path, monkeypatch):
    # --action records the resolved model so the shell can label the panel.
    from dwim import __main__ as m
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr("dwim.action.run_action",
                        lambda intent, *, runner, context, model="haiku": {"answer": "", "commands": []})
    monkeypatch.setattr("dwim.context.gather", lambda: {"cwd": "/c"})
    monkeypatch.setattr("dwim.claude_runner.run", lambda *a, **k: "")
    m.main(["--action", "why is x big", "--tier", "deep"])
    assert (tmp_path / "dwim" / "last_model").read_text() == "sonnet"
    m.main(["--action", "how do I zip"])           # default = fast
    assert (tmp_path / "dwim" / "last_model").read_text() == "haiku"
