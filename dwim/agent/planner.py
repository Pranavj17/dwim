"""Phase 1: run claude -p on the read-only allowlist to produce a structured
plan. No mutating tools are granted, so this pass cannot change anything."""

from dwim import claude_runner
from dwim.agent.plan import parse_plan

PLAN_SYSTEM = (
    "You are dwim's PLANNING pass. Investigate READ-ONLY (Read/Grep/Glob/"
    "dwim-rag/dwim-locate/git status/log/diff only — you have NO write or edit "
    "tools) and produce a concrete plan to accomplish the task.\n"
    "Output ONLY a JSON object, no prose, of the form:\n"
    '{"steps": [{"kind": "edit", "path": "<repo-relative file>", '
    '"diff": "<what changes>", "why": "<reason>"}, '
    '{"kind": "run", "command": "<exact shell command>", "why": "<reason>"}]}\n'
    "List every file you will edit and every command you will run — the user "
    "approves this exact set and execution is confined to it. Do NOT include "
    "git push, force pushes, git reset --hard, or rm -rf; those are not allowed."
)


def make_plan(task, model, timeout, runner=claude_runner.run):
    prompt = f"{PLAN_SYSTEM}\n\nTASK: {task}"
    text, _session = runner(prompt, model, timeout=timeout)
    return parse_plan(text)
