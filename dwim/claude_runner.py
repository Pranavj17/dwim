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


def _is_empty_result(body):
    """True when a tool result carries no real output — either blank or the
    placeholder the Bash tool emits for a command that printed nothing (e.g.
    `git status --short` on a clean repo). We skip rendering those so the stream
    isn't padded with '(… completed with no output)' lines."""
    b = body.strip().lower()
    return (not b) or ("completed with no output" in b) or (b == "no output")


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


def _render_events(lines, sink):
    """Consume stream-json lines, driving `sink` (a _StreamUI or a recording
    stub). Returns (result_text, session_id, got_result). got_result is True iff
    a `result` event was seen — False means the stream was cut short (e.g.
    killed). sink methods: step(desc), output(body), error(desc, status, body)."""
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
                        sink.step(desc)
        elif etype == "user":
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") != "tool_result":
                    continue
                desc = pending.pop(block.get("tool_use_id"), "")
                body = _result_body(block)
                if block.get("is_error"):
                    sink.error(desc, _result_status(block),
                               "" if _is_empty_result(body) else body)
                elif not _is_empty_result(body):
                    sink.output(body)
        elif etype == "result":
            got_result = True
            result_text = ev.get("result", "") or result_text
    return result_text, session_id, got_result


_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def _crumb(desc):
    """One short token for the breadcrumb — the program name (e.g. `dwim-git`,
    `du`, `read`), not the whole command line."""
    parts = desc.split()
    return parts[0] if parts else desc.strip()


def _short(s, n=48):
    s = s.replace("\n", " ").strip()
    return s if len(s) <= n else s[:n - 1] + "…"


def _write_thinking(text):
    """Save the full call+output trace for `dwim thinking` — Python owns this
    file now, so the live stream stays quiet (was tee'd off stderr by zsh)."""
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    d = os.path.join(cache, "dwim")
    try:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "last_thinking"), "w") as f:
            f.write(text)
    except OSError:
        pass


class _StreamUI:
    """Low-noise live view of the agent working: one animated spinner line
    showing the CURRENT step, which collapses to a single breadcrumb when the
    run finishes (`⋯ 4 steps · dwim-git · du · ls`). The full call+output trace
    goes to `dwim thinking`, not dumped inline — that wall of gray was the pain.

    Only the spinner thread writes the live line; the parser thread just updates
    shared state under a lock. On a non-tty (pipe/test) nothing animates — the
    breadcrumb still prints once at the end."""

    def __init__(self, label, out=None):
        self._out = out if out is not None else sys.stderr
        self._label = label
        self._current = ""
        self._steps = []
        self._trace = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._tty = bool(getattr(self._out, "isatty", lambda: False)())

    def start(self):
        if self._tty:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()

    def _spin(self):
        i = 0
        while not self._stop.wait(0.08):
            with self._lock:
                cur = self._current
            frame = _SPINNER[i % len(_SPINNER)]
            line = f"\r\033[K{_GRAY}{frame} {self._label}"
            if cur:
                line += f" · {_short(cur)}"
            self._out.write(line + _RESET)
            self._out.flush()
            i += 1

    # --- sink protocol driven by _render_events ---
    def step(self, desc):
        with self._lock:
            self._current = desc
            self._steps.append(_crumb(desc))
        self._trace.append(f"  › {desc}")

    def output(self, body):
        self._trace.append(_indent_result(body))

    def error(self, desc, status, body):
        with self._lock:
            self._steps.append("✗" + _crumb(desc))
        self._trace.append(f"{_RED}  ✗ {desc}  ({status}){_RESET}")
        if body:
            self._trace.append(_indent_result(body))

    def note(self, msg):
        """A lifecycle notice (resume / gave-up) — updates the spinner subtitle
        and joins the trace, but isn't counted as a step in the breadcrumb."""
        with self._lock:
            self._current = msg
        self._trace.append(f"  {msg}")

    def finish(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.3)
        _write_thinking("\n".join(self._trace))
        if self._tty:
            self._out.write("\r\033[K")   # wipe the spinner line
        crumb = self._breadcrumb()
        if crumb:
            self._out.write(crumb + "\n")
        self._out.flush()

    def _breadcrumb(self):
        if not self._steps:
            return ""
        shown = self._steps[:6]
        more = f" +{len(self._steps) - 6}" if len(self._steps) > 6 else ""
        return (f"{_GRAY}⋯ {len(self._steps)} "
                f"step{'s' if len(self._steps) != 1 else ''} · "
                f"{' · '.join(shown)}{more}{_RESET}")


def _run_once(cmd, sink, timeout):
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
        text, session_id, got_result = _render_events(proc.stdout, sink)
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
    sink = _StreamUI(f"dwim · {model}")
    sink.start()
    try:
        text, session_id, got = _run_once(
            _build_cmd(prompt, model, effort, resume), sink, timeout)
        tries = 0
        while not got and session_id and tries < max_resumes:
            tries += 1
            sink.note(f"⟳ resuming… ({tries}/{max_resumes})")
            text2, sid2, got = _run_once(
                _build_cmd("Continue and give your final answer.",
                           model, effort, session_id), sink, timeout)
            text = text2 or text
            session_id = sid2 or session_id
        if not got and tries >= max_resumes:
            sink.note(f"⚠ gave up after {max_resumes} resumes")
    finally:
        sink.finish()
    return text, session_id
