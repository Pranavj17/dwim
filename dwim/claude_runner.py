"""Invoke `claude -p` as a read-only investigating agent."""

import json
import shutil
import subprocess

# Read-only tools + read-only shell verbs. Mutating bash is NOT allowed, so the
# agent proposes such commands instead of running them.
_ALLOWED = [
    "Read", "Glob", "Grep", "WebSearch",
    "Bash(ls:*)", "Bash(cat:*)", "Bash(git status)", "Bash(git log:*)",
    "Bash(git diff:*)", "Bash(du:*)", "Bash(df:*)", "Bash(grep:*)",
    "Bash(rg:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(pwd)",
]


def run(prompt: str, model: str) -> str:
    if not shutil.which("claude"):
        return '{"answer": "dwim: claude CLI not found — @ palette needs it.", "commands": []}'
    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "json",
        "--allowedTools", *_ALLOWED,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    out = proc.stdout.strip()
    try:
        obj = json.loads(out)
    except json.JSONDecodeError:
        return out
    # claude --output-format json normally wraps the final text in a single
    # {"result": "..."} object. Some CLI versions instead emit a JSON array
    # of stream events, with the final one being {"type": "result", ...,
    # "result": "..."}. Handle both shapes.
    if isinstance(obj, dict):
        return obj.get("result", out)
    if isinstance(obj, list):
        for item in reversed(obj):
            if isinstance(item, dict) and "result" in item:
                return item["result"]
    return out
