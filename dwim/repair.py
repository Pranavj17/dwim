"""Repair a failed command: deterministic command-not-found → Homebrew install."""

import re
import shutil

# binary -> Homebrew formula, when they differ. Unlisted binaries install as
# themselves.
FORMULA_MAP = {
    "fd": "fd", "bat": "bat", "rg": "ripgrep", "http": "httpie",
}

_NOT_FOUND = re.compile(r"command not found:\s*(\S+)|(?:bash|sh|zsh|ksh):\s+(\S+):\s+command not found")


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
