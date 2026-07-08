"""Phase 2: execute the approved plan with mutating tools enabled but every tool
call gated by the PreToolUse confinement hook. Snapshots first for rollback;
bounds iterations; hard-stops (v1) on any off-plan denial."""

import json
import os
import subprocess
import tempfile

_SETTINGS_TEMPLATE = {
    "hooks": {
        "PreToolUse": [
            {"matcher": "Edit|Write|MultiEdit|Bash",
             "hooks": [{"type": "command", "command": "dwim-confine-hook"}]}
        ]
    }
}

# The MCP config the execute phase runs with: empty. `--strict-mcp-config` +
# this file drops the user's MCP servers so their tool schemas don't bloat the
# prompt (the "prompt too long" trap the spike hit).
_EMPTY_MCP = {"mcpServers": {}}

_EXEC_SYSTEM = (
    "Execute the APPROVED plan. You may edit ONLY the planned files and run ONLY "
    "the planned commands — a hook enforces this and will DENY anything else. If "
    "a command's output shows a failure, re-edit the planned files and re-run to "
    "fix it, iterating until the task is done. When done, print a short report: "
    "files changed, final test/command result. Do not attempt git push."
)


def write_approved_plan(plan, path):
    with open(path, "w") as f:
        json.dump({"files": sorted(plan.files()), "commands": plan.commands()}, f)


def snapshot(repo_root, run=subprocess.run):
    r = run(["git", "-C", repo_root, "stash", "create"],
            capture_output=True, text=True)
    h = (getattr(r, "stdout", "") or "").strip()
    return h if getattr(r, "returncode", 1) == 0 and h else None


def _plan_text(plan):
    lines = []
    for i, s in enumerate(plan.steps, 1):
        if s.get("kind") == "edit":
            d = f" — {s['diff']}" if s.get("diff") else ""
            lines.append(f"{i}. edit {s.get('path','')}{d}  ({s.get('why','')})")
        else:
            lines.append(f"{i}. run {s.get('command','')}  ({s.get('why','')})")
    return "\n".join(lines)


def _default_runner(prompt, plan_file, repo_root, cfg):
    # Confined claude -p, using the flag combination Task 0's spike confirmed:
    # --settings loads the PreToolUse hook; --strict-mcp-config + an empty
    # --mcp-config avoids MCP-tool prompt bloat. Both temp files are generated
    # here. The hook reads the approved plan + repo root from the env.
    sf = tempfile.NamedTemporaryFile("w", suffix=".settings.json", delete=False)
    json.dump(_SETTINGS_TEMPLATE, sf)
    sf.close()
    mf = tempfile.NamedTemporaryFile("w", suffix=".mcp.json", delete=False)
    json.dump(_EMPTY_MCP, mf)
    mf.close()
    env = dict(os.environ, DWIM_APPROVED_PLAN=plan_file, DWIM_REPO_ROOT=repo_root)
    cmd = [
        "claude", "-p", prompt,
        "--model", cfg["model"],
        "--allowedTools", "Read", "Grep", "Glob", "Edit", "Write", "Bash",
        "--max-turns", str(cfg["max_iterations"]),   # enforce the iteration cap
        "--strict-mcp-config", "--mcp-config", mf.name,
        "--settings", sf.name,
        "--output-format", "stream-json", "--verbose",
    ]
    try:
        try:
            proc = subprocess.run(cmd, cwd=repo_root, env=env, text=True,
                                  capture_output=True, timeout=cfg["timeout"])
            out = proc.stdout
        except subprocess.TimeoutExpired as e:
            out = e.stdout if isinstance(e.stdout, str) else (
                  e.stdout.decode() if e.stdout else "")
            from dwim.claude_runner import parse_stream_result
            text, session = parse_stream_result(out)
            return (text or "· execute phase timed out — partial changes may be on "
                    "disk; use the rollback hash.", session)
        from dwim.claude_runner import parse_stream_result
        text, session = parse_stream_result(out)
        return text, session
    finally:
        for f in (sf.name, mf.name):
            try:
                os.unlink(f)
            except OSError:
                pass


def execute(plan, repo_root, cfg, task="", runner=_default_runner, snapshotter=snapshot):
    snap = snapshotter(repo_root)
    plan_file = tempfile.NamedTemporaryFile(
        "w", suffix=".plan.json", delete=False).name
    write_approved_plan(plan, plan_file)
    prompt = (f"{_EXEC_SYSTEM}\n\nTASK: {task}\n\nAPPROVED PLAN "
              f"(you may edit only these files and run only these commands):\n"
              f"{_plan_text(plan)}")
    try:
        report, session = runner(prompt, plan_file, repo_root, cfg)
    finally:
        # The hook needs the plan file during the run, so remove it only after
        # the runner returns.
        try:
            os.unlink(plan_file)
        except OSError:
            pass
    return {"snapshot": snap, "session": session, "report": report}
