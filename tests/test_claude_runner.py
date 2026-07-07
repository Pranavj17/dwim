from dwim.claude_runner import _ALLOWED

# Verbs that can execute or mutate — must never appear in the read-only allowlist.
_FORBIDDEN = ("find", "rm", "mv", "cp", "install", "push", "sudo", "tee",
              "dd", "chmod", "chown", "curl", "wget", "xargs", "eval", "sh", "bash")


def test_allowlist_is_read_only():
    joined = " ".join(_ALLOWED).lower()
    for verb in _FORBIDDEN:
        assert f"bash({verb}" not in joined, f"{verb} must not be in the read-only allowlist"


def test_allowlist_has_no_bypass_tokens():
    joined = " ".join(_ALLOWED).lower()
    assert "dangerously" not in joined
    assert "bypass" not in joined


# Positive guard: every allowlist entry must be an explicitly reviewed read-only tool.
# Adding anything new to _ALLOWED forces a conscious update here (and a security review).
_KNOWN_SAFE = {
    "Read", "Glob", "Grep", "WebSearch",
    "Bash(ls:*)", "Bash(cat:*)", "Bash(git status)", "Bash(git log:*)",
    "Bash(git diff:*)", "Bash(du:*)", "Bash(df:*)", "Bash(grep:*)",
    "Bash(rg:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(pwd)",
    "Bash(dwim-locate:*)",
}


def test_allowlist_is_subset_of_known_safe():
    extra = set(_ALLOWED) - _KNOWN_SAFE
    assert not extra, f"unreviewed tools in allowlist (add to _KNOWN_SAFE only after review): {extra}"


def test_run_returns_friendly_json_when_claude_missing(monkeypatch):
    import json
    import dwim.claude_runner as cr
    monkeypatch.setattr(cr.shutil, "which", lambda name: None)

    def _boom(*a, **k):
        raise AssertionError("no subprocess when claude is missing")
    monkeypatch.setattr(cr.subprocess, "run", _boom)
    monkeypatch.setattr(cr.subprocess, "Popen", _boom)

    out, sid = cr.run("anything", "sonnet")
    obj = json.loads(out)
    assert obj["commands"] == []
    assert "claude" in obj["answer"].lower()
    assert sid == ""


def test_build_cmd_effort_and_flags():
    from dwim.claude_runner import _build_cmd
    cmd = _build_cmd("p", "haiku", "low")
    assert "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in cmd
    assert cmd[cmd.index("--effort") + 1] == "low"
    assert cmd[cmd.index("--setting-sources") + 1] == ""
    assert "--effort" not in _build_cmd("p", "haiku", "")


def test_allowlist_has_dwim_locate_not_find_or_fd():
    from dwim.claude_runner import _ALLOWED
    assert "Bash(dwim-locate:*)" in _ALLOWED
    # find/fd must never be directly allowed — dwim-locate is the safe front door.
    assert not any(a.startswith("Bash(find") or a.startswith("Bash(fd") for a in _ALLOWED)


import json


def _events(*evs):
    return [json.dumps(e) for e in evs]


def test_render_marks_denied_tool_call():
    from dwim.claude_runner import _render_events
    lines = _events(
        {"type": "system", "session_id": "sess-1"},
        {"type": "assistant", "session_id": "sess-1", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Bash",
             "input": {"command": "find ~ -delete"}}]}},
        {"type": "user", "session_id": "sess-1", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "is_error": True,
             "content": "permission denied: Bash"}]}},
        {"type": "result", "session_id": "sess-1", "result": "done"},
    )
    out = []
    text, sid, got = _render_events(lines, out.append)
    assert text == "done" and sid == "sess-1" and got is True
    assert "✗" in "\n".join(out)


def test_render_success_has_no_cross():
    from dwim.claude_runner import _render_events
    lines = _events(
        {"type": "assistant", "session_id": "s", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Bash",
             "input": {"command": "du -sh ."}}]}},
        {"type": "user", "session_id": "s", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "4.0K ."}]}},
        {"type": "result", "session_id": "s", "result": "ok"},
    )
    out = []
    text, sid, got = _render_events(lines, out.append)
    assert text == "ok" and sid == "s" and got is True
    assert "✗" not in "\n".join(out)


def test_render_no_result_event_reports_incomplete():
    from dwim.claude_runner import _render_events
    lines = _events(
        {"type": "system", "session_id": "sX"},
        {"type": "assistant", "session_id": "sX", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Bash",
             "input": {"command": "du -ah /"}}]}},
    )  # stream cut off (killed) — no result event
    out = []
    text, sid, got = _render_events(lines, out.append)
    assert sid == "sX" and got is False and text == ""


def test_build_cmd_adds_resume_when_set():
    from dwim.claude_runner import _build_cmd
    assert "--resume" not in _build_cmd("p", "haiku", "")
    cmd = _build_cmd("p", "haiku", "", resume="sess-9")
    assert cmd[cmd.index("--resume") + 1] == "sess-9"


def test_run_resumes_on_timeout_then_completes(monkeypatch):
    # _run_once: first two calls "time out" (got_result False), third completes.
    from dwim import claude_runner as cr
    monkeypatch.setattr(cr.shutil, "which", lambda _x: "/usr/bin/claude")
    seq = [("", "sess-1", False), ("", "sess-1", False), ("final", "sess-1", True)]
    calls = {"n": 0}

    def fake_once(cmd, emit, timeout):
        r = seq[calls["n"]]; calls["n"] += 1
        return r
    monkeypatch.setattr(cr, "_run_once", fake_once)
    text, sid = cr.run("why", "sonnet")
    assert text == "final" and sid == "sess-1"
    assert calls["n"] == 3               # first run + 2 resumes


def test_run_gives_up_after_max_resumes(monkeypatch):
    from dwim import claude_runner as cr
    monkeypatch.setattr(cr.shutil, "which", lambda _x: "/usr/bin/claude")
    calls = {"n": 0}

    def fake_once(cmd, emit, timeout):
        calls["n"] += 1
        return ("partial", "sess-2", False)
    monkeypatch.setattr(cr, "_run_once", fake_once)
    text, sid = cr.run("why", "sonnet")
    assert text == "partial" and sid == "sess-2"
    assert calls["n"] == 3               # initial + exactly 2 resumes


def test_run_keeps_last_session_id_when_resume_returns_empty(monkeypatch):
    from dwim import claude_runner as cr
    monkeypatch.setattr(cr.shutil, "which", lambda _x: "/usr/bin/claude")
    seq = [("", "sess-A", False), ("", "", False), ("final", "sess-A", True)]
    calls = {"n": 0}

    def fake_once(cmd, emit, timeout):
        r = seq[calls["n"]]; calls["n"] += 1
        return r
    monkeypatch.setattr(cr, "_run_once", fake_once)
    text, sid = cr.run("why", "sonnet")
    assert text == "final" and sid == "sess-A" and calls["n"] == 3


def test_run_no_resume_on_clean_completion(monkeypatch):
    from dwim import claude_runner as cr
    monkeypatch.setattr(cr.shutil, "which", lambda _x: "/usr/bin/claude")
    calls = {"n": 0}

    def fake_once(cmd, emit, timeout):
        calls["n"] += 1
        return ("ok", "sess-3", True)
    monkeypatch.setattr(cr, "_run_once", fake_once)
    text, sid = cr.run("q", "haiku")
    assert text == "ok" and sid == "sess-3" and calls["n"] == 1


def test_run_missing_claude_returns_tuple(monkeypatch):
    from dwim import claude_runner as cr
    monkeypatch.setattr(cr.shutil, "which", lambda _x: None)
    text, sid = cr.run("q", "haiku")
    assert "claude CLI not found" in text and sid == ""


def test_run_once_caps_wall_clock_via_process_group():
    # A sh child that backgrounds a long sleep holding stdout: without a
    # process-group kill the read blocks the full 30s despite timeout=1.
    import os as _os, time
    import pytest
    if not hasattr(_os, "killpg"):
        pytest.skip("POSIX process groups only")
    from dwim.claude_runner import _run_once
    start = time.monotonic()
    text, sid, got = _run_once(["sh", "-c", "sleep 30 & wait"],
                               lambda s: None, timeout=1)
    elapsed = time.monotonic() - start
    assert elapsed < 8, f"watchdog did not cap wall-clock: {elapsed:.1f}s"
    assert got is False   # killed before any result event
