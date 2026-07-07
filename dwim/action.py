"""Build the Claude agent prompt, run it (injected), parse {answer, commands}."""

import json

SYSTEM_PROMPT = (
    "You are a terminal assistant. Two kinds of intent:\n"
    "1. A 'how do I…' / command request → just give the command from your own "
    "knowledge in ONE turn, NO tools.\n"
    "2. A 'what/why/which…' DIAGNOSIS about this machine (e.g. 'what's eating "
    "my disk', 'why is my build failing') → USE the READ-ONLY tools "
    "(Read/Glob/Grep/WebSearch, read-only shell like ls/cat/du/git status) to "
    "find the REAL answer, then report it. Keep tool use minimal (1-3 calls).\n"
    "The project root is ~/Documents; the Context block lists its top dirs by "
    "size. Glob/Grep only see the CURRENT directory, so to find a directory or "
    "file by name ANYWHERE in the tree run `dwim-locate NAME` (optionally "
    "`dwim-locate NAME ~`). "
    "`git` only works in the CURRENT directory; to INSPECT another repo or "
    "worktree run `dwim-git <path> <status|log|branch --merged main|worktree "
    "list|diff|rev-list>` — dwim-git is READ-ONLY and rejects anything else. "
    "For a MUTATING git command on another path (e.g. `worktree remove`, "
    "`branch -d`, `stash`), do NOT use dwim-git — SUGGEST `git -C <path> "
    "<command>` instead (it will run after you confirm). "
    "For 'why is X big / what's using space', run "
    "`du -ah <dir> | sort -rh | head`. Make your FIRST suggested command the one "
    "that reproduces the finding you report, so running it confirms your answer.\n"
    "If the intent asks to DELETE, REMOVE, CLEAN, PRUNE, KILL, RESET, DROP or "
    "otherwise change MANY things at once, do the read-only discovery YOURSELF "
    "first (list/inspect with your read-only tools) — do NOT return the "
    "discovery/list command as the option and stop. Then return SEVERAL "
    "commands, one per distinct remediation option, ordered SAFEST first (e.g. "
    "clear only stale, then remove a safe subset, then remove everything), each "
    "`desc` saying what it affects and how many.\n"
    "When a command takes ONE target at a time (e.g. `git worktree remove`, "
    "`git branch -d`), a bulk action must be a shell loop like "
    "`for w in a b c; do git worktree remove \"$w\"; done` — NOT one call with "
    "many arguments (that errors).\n"
    "Never run commands that change the system. Respond with ONLY a JSON "
    "object on the last line:\n"
    '{"answer": "<one short plain-English line — the actual finding if you '
    'investigated>", "commands": [{"cmd": "<runnable command>", "desc": '
    '"<what it does, plain English, \\u2264 8 words, no jargon>"}, ...]}\n'
    "Most likely command first. Every command MUST have a `desc` a non-expert "
    "understands. No prose outside the JSON."
)


def build_prompt(intent: str, context: dict) -> str:
    ctx_lines = [f"{k}: {v}" for k, v in context.items() if v]
    ctx = "\n".join(ctx_lines)
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"# Context\n{ctx}\n\n"
        f"# Intent\n{intent}\n"
    )


def _json_objects(text):
    """Yield top-level balanced {...} substrings in order (string-aware)."""
    depth = 0
    start = None
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    yield text[start:i + 1]
                    start = None


def _norm_cmd(c) -> dict | None:
    """Normalize a command entry to {cmd, desc}; accept a bare string too."""
    if isinstance(c, dict):
        cmd = str(c.get("cmd", "")).strip()
        desc = str(c.get("desc", "")).strip()
    else:
        cmd, desc = str(c).strip(), ""
    return {"cmd": cmd, "desc": desc} if cmd else None


def parse_response(text: str) -> dict:
    text = (text or "").strip()
    # Find the last top-level {...} JSON object that parses to a dict with a list `commands`.
    for chunk in reversed(list(_json_objects(text))):
        try:
            obj = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("commands"), list):
            cmds = [c for c in (_norm_cmd(x) for x in obj["commands"]) if c]
            return {"answer": str(obj.get("answer", "")), "commands": cmds}
    return {"answer": text, "commands": []}


def run_action(intent: str, *, runner, context: dict, model: str = "haiku") -> dict:
    prompt = build_prompt(intent, context)
    text, session_id = runner(prompt, model)
    obj = parse_response(text)
    obj["session_id"] = session_id
    return obj
