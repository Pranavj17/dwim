"""Build the Claude agent prompt, run it (injected), parse {answer, commands}."""

import json

SYSTEM_PROMPT = (
    "You are a FAST terminal assistant. The user wants a COMMAND to run — not "
    "for you to do the work yourself. In almost every case, answer from your "
    "own knowledge in ONE turn and do NOT run any tools. Only use a READ-ONLY "
    "tool (Read/Glob/Grep/WebSearch, read-only shell) if the intent EXPLICITLY "
    "asks you to diagnose/find something specific on this machine that is "
    "impossible to answer otherwise (e.g. 'why is X failing', 'what's eating "
    "my disk'). Default: NO tools, instant answer. Never run commands that "
    "change the system. Respond with ONLY a JSON object on the last line:\n"
    '{"answer": "<one short plain-English line>", "commands": '
    '[{"cmd": "<runnable command>", "desc": "<what it does, plain English, '
    '\\u2264 8 words, no jargon>"}, ...]}\n'
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
    return parse_response(runner(prompt, model))
