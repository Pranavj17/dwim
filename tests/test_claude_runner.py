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

    out = cr.run("anything", "sonnet")
    obj = json.loads(out)
    assert obj["commands"] == []
    assert "claude" in obj["answer"].lower()


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
