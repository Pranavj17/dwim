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
