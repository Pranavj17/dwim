"""Repair a failed command: deterministic command-not-found → Homebrew install."""

import re
import shutil

# binary -> Homebrew formula, when they differ. Unlisted binaries install as
# themselves.
FORMULA_MAP = {
    "fd": "fd", "bat": "bat", "rg": "ripgrep", "http": "httpie",
}

_NOT_FOUND = re.compile(r"command not found: (\S+)|(?!.*command not found:)(\S+): command not found")


def missing_binary(cmd: str, stderr: str) -> str | None:
    m = _NOT_FOUND.search(stderr or "")
    if not m:
        return None
    return m.group(1) or m.group(2)


def install_suggestion(binary: str, *, has_brew=None) -> dict | None:
    if has_brew is None:
        has_brew = shutil.which("brew") is not None
    if not has_brew or not binary:
        return None
    formula = FORMULA_MAP.get(binary, binary)
    return {"cmd": f"brew install {formula}",
            "desc": f"install {binary} with Homebrew"}


from dwim.action import parse_response


def _history_prompt(history: list, last: dict) -> str:
    lines = ["A command the user is trying to accomplish failed. Suggest the "
             "next command(s) to fix it. Respond with ONLY the JSON object "
             '{"answer": "<one line>", "commands": [{"cmd": "...", '
             '"desc": "..."}]}.', "", "# What was tried"]
    for h in history:
        lines.append(f"$ {h['cmd']}  (exit {h.get('exit')})")
        err = (h.get("stderr") or h.get("stdout") or "").strip()
        if err:
            lines.append(f"  → {err[:400]}")
    lines += ["", "# Now suggest the fix for the last failure above."]
    return "\n".join(lines)


def repair(history: list, last: dict, *, runner) -> list:
    # Deterministic first: command-not-found -> Homebrew install.
    binary = missing_binary(last.get("cmd", ""), last.get("stderr", ""))
    if binary:
        sug = install_suggestion(binary)
        if sug:
            return [sug]
    # Fallback: ask Claude with the full history text.
    parsed = parse_response(runner(_history_prompt(history, last), "haiku"))
    return parsed.get("commands", [])
