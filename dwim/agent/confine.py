"""The deterministic gate the PreToolUse hook consults for every tool call in
the execute phase. Decides allow/deny from the approved plan + a hard denylist
that overrides approval. Pure and total — no I/O, no model."""

import fnmatch
import os
import re

# Read-only tools + read-only Bash verbs: always allowed, never in the plan.
_RO_TOOLS = {"Read", "Grep", "Glob", "WebSearch"}
_RO_BASH = re.compile(
    r"^\s*(ls|cat|pwd|du|df|grep|rg|head|tail|dwim-locate|dwim-rag|dwim-git|"
    r"git\s+(status|log|diff|show|branch\s*$))\b")

# Hard denylist: denied unconditionally, even if present in the approved plan.
_DENY_CMD = re.compile(
    r"(^|\s|&&|\|\||;)\s*("
    r"git\s+push|"
    r"git\s+reset\s+--hard|"
    r"rm\s+-[rf]|"
    r"git\s+.*--force|git\s+.*\s-f(\s|$)"
    r")")
_CRED = ["*.pem", "*.key", ".env", ".env.*", "id_*", "*credential*", "*secret*"]


def _abs(path, root):
    if not path:
        return None
    p = path if os.path.isabs(path) else os.path.join(root, path)
    return os.path.normpath(p)


def _in_repo(abspath, root):
    root = os.path.normpath(root)
    return abspath == root or abspath.startswith(root + os.sep)


def _is_credential(abspath):
    base = os.path.basename(abspath)
    return any(fnmatch.fnmatch(base, pat) for pat in _CRED)


def decide(tool, inp, approved_files, approved_cmds, repo_root):
    inp = inp or {}
    if tool in _RO_TOOLS:
        return "allow", "read-only tool"

    if tool == "Bash":
        cmd = inp.get("command", "") or ""
        if _DENY_CMD.search(cmd):
            return "deny", "hard-denied command (never auto-run)"
        if _RO_BASH.match(cmd):
            return "allow", "read-only command"
        if cmd.strip() in [c.strip() for c in approved_cmds]:
            return "allow", "command in approved plan"
        return "deny", "command not in approved plan"

    if tool in ("Edit", "Write", "MultiEdit"):
        abspath = _abs(inp.get("file_path"), repo_root)
        if abspath is None or not _in_repo(abspath, repo_root):
            return "deny", "path outside repo"
        if _is_credential(abspath):
            return "deny", "credential file (never written)"
        approved_abs = {_abs(f, repo_root) for f in approved_files}
        if abspath in approved_abs:
            return "allow", "edit to approved path"
        return "deny", "path not in approved plan"

    return "deny", f"tool {tool} not permitted in confined execution"
