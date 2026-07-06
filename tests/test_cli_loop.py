import json
import os
import subprocess
import sys


def _run(args, stdin=None):
    # Inherit the real environment (so `brew`, `less`, etc. are on PATH); just
    # add PYTHONPATH so `-m dwim` resolves from the repo root pytest runs in.
    env = {**os.environ, "PYTHONPATH": "."}
    return subprocess.run([sys.executable, "-m", "dwim", *args],
                          capture_output=True, text=True, input=stdin,
                          env=env)


def test_run_readonly_executes_and_reports_json():
    p = _run(["--run", "echo hi"])
    obj = json.loads(p.stdout.strip())
    assert obj["read_only"] is True
    assert obj["interactive"] is False
    assert obj["exit"] == 0
    assert obj["stdout"].strip() == "hi"


def test_run_interactive_present_is_handed_off():
    p = _run(["--run", "less /etc/hosts"])   # less exists on macOS/Linux
    obj = json.loads(p.stdout.strip())
    assert obj["interactive"] is True
    assert obj["ran"] is False
    assert obj["exit"] is None       # present interactive tool → handed off, NOT run


def test_run_interactive_missing_reports_not_found():
    import shutil
    if shutil.which("ncdu"):
        import pytest
        pytest.skip("ncdu is installed in this env")
    p = _run(["--run", "ncdu ~/x"])
    obj = json.loads(p.stdout.strip())
    assert obj["interactive"] is True
    assert obj["exit"] == 127         # missing interactive tool → not-found, loop will repair


def test_run_mutating_not_executed_without_force():
    p = _run(["--run", "true"])       # "true" is not on the read-only verb set → mutating
    obj = json.loads(p.stdout.strip())
    assert obj["read_only"] is False
    assert obj["ran"] is False
    assert obj["exit"] is None       # NOT run without --force (safety)


def test_run_mutating_executed_with_force():
    p = _run(["--run", "true", "--force"])
    obj = json.loads(p.stdout.strip())
    assert obj["ran"] is True
    assert obj["exit"] == 0           # ran because approved via --force


def test_repair_reads_history_prints_candidates():
    history = json.dumps([{"cmd": "ncdu ~/x", "exit": 127, "stdout": "",
                           "stderr": "zsh: command not found: ncdu"}])
    p = _run(["--repair"], stdin=history)
    line = p.stdout.strip().splitlines()[0]
    desc, tab, cmd = line.partition("\t")
    assert cmd == "brew install ncdu"
    assert desc          # non-empty description


def test_repair_empty_history_returns_no_candidates_without_claude():
    p = _run(["--repair"], stdin="")          # empty stdin
    assert p.stdout.strip() == ""             # no candidates
    assert p.returncode == 0

    p2 = _run(["--repair"], stdin="[]")        # empty array
    assert p2.stdout.strip() == ""
    assert p2.returncode == 0


def test_repair_nonlist_json_returns_zero_without_traceback():
    p = _run(["--repair"], stdin='{"cmd":"x"}')       # well-formed JSON, not a list
    assert p.returncode == 0
    assert p.stdout.strip() == ""
    assert "Traceback" not in p.stderr

    p2 = _run(["--repair"], stdin="5")                 # well-formed JSON scalar
    assert p2.returncode == 0
    assert p2.stdout.strip() == ""
    assert "Traceback" not in p2.stderr


def test_run_interactive_not_executed_even_with_force():
    p = _run(["--run", "less /etc/hosts", "--force"])   # less exists; interactive
    obj = json.loads(p.stdout.strip())
    assert obj["interactive"] is True
    assert obj["ran"] is False               # NEVER executed, even with --force
    assert obj["exit"] is None
