"""Read-only local context handed to the Claude agent."""

import os
import subprocess


def _run(cmd) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=2).stdout.strip()
    except Exception:
        return ""


def gather() -> dict:
    cwd = os.getcwd()
    git = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    state = os.path.expanduser("~/.cache/dwim/last")
    last_cmd, last_exit = "", ""
    if os.path.exists(state):
        with open(state) as f:
            lines = f.read().splitlines()
        if lines:
            last_exit = lines[0]
            last_cmd = "\n".join(lines[1:])
    ls = _run(["ls", "-a"])[:800]
    return {"cwd": cwd, "git": git, "last_cmd": last_cmd,
            "last_exit": last_exit, "ls": ls}
