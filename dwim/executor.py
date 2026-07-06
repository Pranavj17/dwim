"""Classify a shell command (interactive? read-only?) and run captured commands."""

import re
import shlex
import subprocess

# Full-screen/interactive tools — never captured or auto-run; handed to the shell.
INTERACTIVE = frozenset({
    "ncdu", "htop", "top", "vim", "vi", "nano", "less", "more",
    "man", "ssh", "tmux", "fzf", "watch",
})

# Read-only FILTER verbs (consume stdin, never write/execute) — a superset of
# claude_runner._ALLOWED's shell verbs, so common pipelines auto-run. Anything
# that can write (tee, sed -i) or execute (awk system(), xargs) is excluded.
READ_ONLY_VERBS = frozenset({
    "ls", "cat", "du", "df", "grep", "rg", "head", "tail", "pwd", "echo", "git",
    "sort", "uniq", "wc", "cut", "tr", "column", "nl", "rev", "comm", "fold",
})
_READ_ONLY_GIT_SUB = frozenset({"status", "log", "diff"})  # mirror _ALLOWED

# Benign redirects to strip before scanning: >/dev/null, 2>/dev/null,
# &>/dev/null (anchored so /dev/nullx etc. are NOT matched), and fd-dups like
# 2>&1 (digits required on both sides so >&word is NOT treated as benign).
_BENIGN_REDIR = re.compile(r"(?:&>|\d*>>?)\s*/dev/null(?=\s|$)|\d+>&\d+")


def first_binary(cmd: str) -> str:
    """The command's first token (the binary being invoked)."""
    try:
        parts = shlex.split(cmd)
    except ValueError:
        parts = cmd.split()
    return parts[0] if parts else ""


def is_interactive(cmd: str) -> bool:
    return first_binary(cmd) in INTERACTIVE


def _segment_read_only(seg: str) -> bool:
    verb = first_binary(seg)
    if not verb:
        return False
    if verb == "git":
        parts = seg.split()
        return len(parts) > 1 and parts[1] in _READ_ONLY_GIT_SUB
    return verb in READ_ONLY_VERBS


def is_read_only(cmd: str) -> bool:
    if not cmd.strip():
        return False
    probe = _BENIGN_REDIR.sub(" ", cmd)
    segments = [""]
    in_single = in_double = False
    i, n = 0, len(probe)
    while i < n:
        c = probe[i]
        two = probe[i:i + 2]
        # Backslash escapes the next char OUTSIDE single quotes (single quotes
        # take everything literally). Keep both chars literal so \' / \" / \$
        # never toggle quote state or start substitution.
        if c == "\\" and not in_single:
            segments[-1] += probe[i:i + 2]
            i += 2
            continue
        if in_single:
            if c == "'":
                in_single = False
            segments[-1] += c
            i += 1
            continue
        if in_double:
            # Double quotes suppress word-splitting/globbing but NOT command
            # substitution — $( ) and backticks still execute inside them.
            if two == "$(" or c == "`":
                return False
            if c == '"':
                in_double = False
            segments[-1] += c
            i += 1
            continue
        # Unquoted context:
        if c == "'":
            in_single = True
            segments[-1] += c
            i += 1
            continue
        if c == '"':
            in_double = True
            segments[-1] += c
            i += 1
            continue
        if two == "$(" or c == "`":
            return False                      # command substitution
        if c in "()":
            return False                      # subshell grouping
        if c in "<>":
            return False                      # redirect (benign /dev/null already stripped)
        if c in ";&\n":
            return False                      # chain / background / newline
        if c == "|":
            if two == "||":
                return False
            segments.append("")
            i += 1
            continue
        segments[-1] += c
        i += 1
    if in_single or in_double:
        return False                          # unterminated quote → fail safe
    return all(_segment_read_only(s) for s in segments)


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
