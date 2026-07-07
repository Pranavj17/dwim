"""Invoke `claude -p` as a read-only investigating agent, streaming its actions."""

import json
import os
import shutil
import signal
import subprocess
import sys
import threading

# Read-only tools + read-only shell verbs. Mutating bash is NOT allowed, so the
# agent proposes such commands instead of running them.
_ALLOWED = [
    "Read", "Glob", "Grep", "WebSearch",
    "Bash(ls:*)", "Bash(cat:*)", "Bash(git status:*)",
    "Bash(git worktree list:*)", "Bash(git log:*)",
    "Bash(git diff:*)", "Bash(du:*)", "Bash(df:*)", "Bash(grep:*)",
    "Bash(rg:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(pwd)",
    "Bash(dwim-locate:*)",     # read-only by construction: name+root only, no flags
    "Bash(dwim-git:*)",        # read-only by construction: positive-allowlisted subcommands only
]

_GRAY = "\033[38;5;244m"
_RED = "\033[38;5;203m"
_RESET = "\033[0m"


def _build_cmd(prompt: str, model: str, effort: str, resume: str = "") -> list:
    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        # stream-json lets us surface the agent's tool calls live as it works.
        "--output-format", "stream-json", "--verbose",
        "--allowedTools", *_ALLOWED,
        # Speed: skip the user's MCP servers and project settings/hooks (~5s of
        # startup tax). Built-in tools still work; the agent runs in the cwd.
        "--strict-mcp-config",
        "--setting-sources", "",
    ]
    if resume:
        cmd += ["--resume", resume]
    if effort:
        cmd += ["--effort", effort]
    return cmd


def _tool_desc(block: dict) -> str:
    """A short human label for a tool_use block, shown live in gray."""
    name = block.get("name", "")
    inp = block.get("input", {}) or {}
    if name == "Bash":
        return inp.get("command", "")
    if name == "Read":
        return "read " + os.path.basename(inp.get("file_path", ""))
    if name in ("Grep", "Glob"):
        return f"{name.lower()} {inp.get('pattern') or inp.get('query', '')}"
    if name == "WebSearch":
        return "search: " + inp.get("query", "")
    return name


def _result_status(block: dict) -> str:
    text = str(block.get("content", "")).lower()
    return "denied" if ("permission" in text or "denied" in text) else "failed"


_RESULT_MAX_LINES = 6
_RESULT_MAX_CHARS = 400


def _result_body(block):
    """Extract the text of a tool_result (content is a str or a list of blocks)."""
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(b.get("text", "") for b in c
                       if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _indent_result(text):
    """Dim, indent, and truncate a tool result for the live stream."""
    text = text.strip()
    if len(text) > _RESULT_MAX_CHARS:
        text = text[:_RESULT_MAX_CHARS]
    lines = text.splitlines()
    shown = lines[:_RESULT_MAX_LINES]
    body = "\n".join(f"{_GRAY}    {ln}{_RESET}" for ln in shown)
    extra = len(lines) - _RESULT_MAX_LINES
    if extra > 0:
        body += f"\n{_GRAY}    … (+{extra} lines){_RESET}"
    return body


def _render_events(lines, emit):
    """Consume stream-json lines; emit display lines. Returns
    (result_text, session_id, got_result). got_result is True iff a `result`
    event was seen — False means the stream was cut short (e.g. killed)."""
    result_text = ""
    session_id = ""
    got_result = False
    pending = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not session_id:
            session_id = ev.get("session_id", "") or session_id
        etype = ev.get("type")
        if etype == "assistant":
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    desc = _tool_desc(block)
                    if desc:
                        pending[block.get("id")] = desc
                        emit(f"{_GRAY}  › {desc}{_RESET}")
        elif etype == "user":
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") != "tool_result":
                    continue
                desc = pending.pop(block.get("tool_use_id"), "")
                body = _result_body(block)
                if block.get("is_error"):
                    if desc:
                        emit(f"{_RED}  ✗ {desc}  ({_result_status(block)}){_RESET}")
                    if body.strip():
                        emit(_indent_result(body))
                elif body.strip():
                    emit(_indent_result(body))
        elif etype == "result":
            got_result = True
            result_text = ev.get("result", "") or result_text
    return result_text, session_id, got_result


def _run_once(cmd, emit, timeout):
    """One claude -p invocation with a real wall-clock cap: a watchdog kills the
    whole process group after `timeout`s (the stream read is otherwise unbounded,
    and a descendant holding stdout would keep it open). Returns
    (text, session_id, got_result)."""
    # stdin=DEVNULL is critical: claude -p reads stdin, so an inherited terminal
    # stdin makes it (a) wait ~3s for input every run and (b) SWALLOW the user's
    # keystrokes (up-arrow/Enter go to claude, not the blocked shell). DEVNULL
    # gives it immediate EOF.
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True,
                            start_new_session=True)  # own group → kill the tree

    def _kill():
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    watchdog = threading.Timer(timeout, _kill)
    watchdog.start()
    try:
        text, session_id, got_result = _render_events(proc.stdout, emit)
    finally:
        watchdog.cancel()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _kill()
            proc.wait()
    return text, session_id, got_result


def run(prompt: str, model: str, effort: str = "", resume: str = "",
        max_resumes: int = 2, timeout: int = 120):
    """Run the agent, returning (result_text, session_id). `resume` continues an
    existing session. If a run is killed by the timeout before finishing, resume
    the same session up to `max_resumes` times to let it complete."""
    if not shutil.which("claude"):
        return ('{"answer": "dwim: claude CLI not found — @ palette needs it.", '
                '"commands": []}', "")
    emit = lambda s: print(s, file=sys.stderr, flush=True)
    text, session_id, got = _run_once(
        _build_cmd(prompt, model, effort, resume), emit, timeout)
    tries = 0
    while not got and session_id and tries < max_resumes:
        tries += 1
        emit(f"{_GRAY}  ⟳ resuming… ({tries}/{max_resumes}){_RESET}")
        text2, sid2, got = _run_once(
            _build_cmd("Continue and give your final answer.",
                       model, effort, session_id), emit, timeout)
        text = text2 or text
        session_id = sid2 or session_id
    if not got and tries >= max_resumes:
        emit(f"{_RED}  ⚠ gave up after {max_resumes} resumes{_RESET}")
    return text, session_id
