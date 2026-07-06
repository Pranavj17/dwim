"""Build the Claude agent prompt, run it (injected), parse {answer, commands}."""

import json
import re

SYSTEM_PROMPT = (
    "You are a terminal action assistant. The user gives an intent. Investigate "
    "freely using READ-ONLY tools (Read, Glob, Grep, WebSearch, and read-only "
    "shell like ls/cat/git status/du/grep). Do NOT run commands that change the "
    "system. Respond with ONLY a JSON object on the last line:\n"
    '{"answer": "<one-line answer or empty>", "commands": ["<runnable command>", ...]}\n'
    "Put the command(s) the user should run in `commands` (most likely first). "
    "No prose outside the JSON."
)


def build_prompt(intent: str, context: dict) -> str:
    ctx_lines = [f"{k}: {v}" for k, v in context.items() if v]
    ctx = "\n".join(ctx_lines)
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"# Context\n{ctx}\n\n"
        f"# Intent\n{intent}\n"
    )


def parse_response(text: str) -> dict:
    text = (text or "").strip()
    # Find the last {...} JSON object in the output.
    matches = re.findall(r"\{.*\}", text, re.DOTALL)
    for chunk in reversed(matches):
        try:
            obj = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "commands" in obj:
            cmds = [str(c) for c in obj.get("commands", []) if str(c).strip()]
            return {"answer": str(obj.get("answer", "")), "commands": cmds}
    return {"answer": text, "commands": []}


def run_action(intent: str, *, runner, context: dict, model: str = "sonnet") -> dict:
    prompt = build_prompt(intent, context)
    return parse_response(runner(prompt, model))
