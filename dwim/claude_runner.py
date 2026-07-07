"""Invoke `claude -p` as a read-only investigating agent, streaming its actions."""

import json
import os
import shutil
import subprocess
import sys

# Read-only tools + read-only shell verbs. Mutating bash is NOT allowed, so the
# agent proposes such commands instead of running them.
_ALLOWED = [
    "Read", "Glob", "Grep", "WebSearch",
    "Bash(ls:*)", "Bash(cat:*)", "Bash(git status)", "Bash(git log:*)",
    "Bash(git diff:*)", "Bash(du:*)", "Bash(df:*)", "Bash(grep:*)",
    "Bash(rg:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(pwd)",
    "Bash(dwim-locate:*)",     # read-only by construction: name+root only, no flags
]

_GRAY = "\033[38;5;244m"
_RED = "\033[38;5;203m"
_RESET = "\033[0m"


def _build_cmd(prompt: str, model: str, effort: str) -> list:
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
                if block.get("type") == "tool_result" and block.get("is_error"):
                    desc = pending.pop(block.get("tool_use_id"), "")
                    if desc:
                        emit(f"{_RED}  ✗ {desc}  ({_result_status(block)}){_RESET}")
        elif etype == "result":
            got_result = True
            result_text = ev.get("result", "") or result_text
    return result_text, session_id, got_result


def run(prompt: str, model: str, effort: str = "") -> str:
    if not shutil.which("claude"):
        return '{"answer": "dwim: claude CLI not found — @ palette needs it.", "commands": []}'
    proc = subprocess.Popen(
        _build_cmd(prompt, model, effort),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    result_text, _session_id, _got = _render_events(
        proc.stdout,
        lambda s: print(s, file=sys.stderr, flush=True),
    )
    try:
        proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
    return result_text
