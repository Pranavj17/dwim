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
