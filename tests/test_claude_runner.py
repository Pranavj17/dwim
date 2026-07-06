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
}


def test_allowlist_is_subset_of_known_safe():
    extra = set(_ALLOWED) - _KNOWN_SAFE
    assert not extra, f"unreviewed tools in allowlist (add to _KNOWN_SAFE only after review): {extra}"
