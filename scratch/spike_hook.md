# Task 0 Spike — claude -p PreToolUse hard-deny + resume

**Result: CONFIRMED. Build the hook-confined design as planned.**

## Proven
- Headless `claude -p` runs a PreToolUse hook and **hard-denies** the tool call.
  Verified: asked it to Write hello.txt with a hook denying Write → final result
  carried `"permission_denials":[{"tool_name":"Write",...}]`, the Write tool_result
  was `is_error:true` ("denied"), and **hello.txt was never created**. Run still
  exited `"subtype":"success"`.
- Deny JSON shape the hook must emit (stdout):
  `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",
    "permissionDecisionReason":"..."}}`  (allow = same with "allow").
- **Off-plan detection for v1 hard-stop report:** parse the final result message's
  `permission_denials[]` (tool_name + tool_input) → "needs <X> — re-run with it in scope".

## Proven flag combination for the EXECUTE phase (use verbatim in Task 8)
    claude -p "<exec system prompt>" \
      --model <sonnet> \
      --allowedTools Read Grep Glob Edit Write Bash \
      --max-turns <cap> \
      --strict-mcp-config --mcp-config <empty-mcp.json> \
      --settings <hook-settings.json> \
      --output-format stream-json --verbose
  with env DWIM_APPROVED_PLAN=<plan.json> DWIM_REPO_ROOT=<repo root>, cwd = repo root.
  - `--settings <file>` is what loads the hook (NOT `--setting-sources ""`, which the
    read-only runner uses to DISABLE hooks).
  - `--strict-mcp-config --mcp-config <empty {"mcpServers":{}}>` avoids the nested
    "prompt too long" MCP-tool bloat. Task 8's `_default_runner` must generate BOTH
    the empty-mcp file and the settings file (temp).
  - Multiple PreToolUse hooks compose with deny-wins, so co-existing user hooks
    (e.g. remember) don't weaken confinement.

## Resume (fast-follow only)
- `--resume <session_id>` already used by `claude_runner.run`; not required for v1
  (inline off-plan re-gate is the fast-follow). Treat as proven by existing code.
