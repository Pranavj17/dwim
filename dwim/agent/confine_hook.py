"""PreToolUse hook entrypoint for the execute phase. Reads Claude's hook JSON on
stdin, consults the approved plan + confine.decide, and emits the allow/deny
decision. Fails CLOSED (deny) on any parse error — a hook that can't decide must
not permit a mutation."""

import json
import os
import sys

from dwim.agent.confine import decide


def _out(decision, reason):
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }})


def run_hook(stdin_text, plan_json, repo_root):
    try:
        ev = json.loads(stdin_text)
        tool = ev.get("tool_name", "")
        inp = ev.get("tool_input", {}) or {}
    except (ValueError, TypeError):
        return _out("deny", "unparseable hook input — failing closed")
    files = set(plan_json.get("files", []))
    cmds = list(plan_json.get("commands", []))
    decision, reason = decide(tool, inp, files, cmds, repo_root)
    return _out(decision, reason)


def main():
    plan_path = os.environ.get("DWIM_APPROVED_PLAN", "")
    root = os.environ.get("DWIM_REPO_ROOT", os.getcwd())
    try:
        with open(plan_path) as f:
            plan_json = json.load(f)
    except (OSError, ValueError):
        plan_json = {"files": [], "commands": []}
    sys.stdout.write(run_hook(sys.stdin.read(), plan_json, root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
