"""Classify a shell command (interactive? read-only?) and run captured commands."""

import shlex
import subprocess

# Full-screen/interactive tools — never captured or auto-run; handed to the shell.
INTERACTIVE = frozenset({
    "ncdu", "htop", "top", "vim", "vi", "nano", "less", "more",
    "man", "ssh", "tmux", "fzf", "watch",
})

# Read-only verbs — kept in sync with dwim/claude_runner.py::_ALLOWED. `find` is
# deliberately excluded (find -exec/-delete can execute/mutate).
READ_ONLY_VERBS = frozenset({
    "ls", "cat", "du", "df", "grep", "rg", "head", "tail", "pwd",
    "echo", "git",  # only read-only git subcommands (guarded below)
})
_READ_ONLY_GIT_SUB = frozenset({"status", "log", "diff", "show", "branch"})


def first_binary(cmd: str) -> str:
    """The command's first token (the binary being invoked)."""
    try:
        parts = shlex.split(cmd)
    except ValueError:
        parts = cmd.split()
    return parts[0] if parts else ""


def is_interactive(cmd: str) -> bool:
    return first_binary(cmd) in INTERACTIVE


def is_read_only(cmd: str) -> bool:
    try:
        parts = shlex.split(cmd)
    except ValueError:
        parts = cmd.split()
    if not parts:
        return False
    verb = parts[0]
    if verb == "git":
        return len(parts) > 1 and parts[1] in _READ_ONLY_GIT_SUB
    return verb in READ_ONLY_VERBS


def run_captured(cmd: str, *, timeout: int = 30, cap: int = 4000) -> dict:
    """Run a non-interactive command, capturing output. Never raises."""
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout)
        return {"exit": p.returncode, "stdout": p.stdout[:cap],
                "stderr": p.stderr[:cap], "timed_out": False}
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "")
        err = (e.stderr or "")
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        return {"exit": 124, "stdout": out[:cap], "stderr": err[:cap],
                "timed_out": True}
