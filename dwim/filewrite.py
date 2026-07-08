"""Write the last @ answer to a file. The @ agent proposes a consent-gated
`dwim-write <path>`; after the user approves at the gate, this writes the answer
they just saw (stored in the cache) to <path>. Content lives in the cache file,
NOT in the command, so the single-line command channel (which drops heredocs)
is a non-issue. Never raises — mirrors executor.run_captured's contract."""

import os


def _cache_dir() -> str:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "dwim")


def last_answer_path() -> str:
    return os.path.join(_cache_dir(), "last_answer")


def store_answer(text: str) -> None:
    """Best-effort: persist the raw answer so a later dwim-write can save it.
    Swallows OSError (same posture as the last_model/last_session writes)."""
    try:
        os.makedirs(_cache_dir(), exist_ok=True)
        with open(last_answer_path(), "w") as f:
            f.write(text or "")
    except OSError:
        pass


def write_last_answer(path: str) -> tuple[bool, str]:
    """Write the stored last answer to `path`. Returns (ok, message). Never raises."""
    try:
        with open(last_answer_path()) as f:
            content = f.read()
    except OSError:
        content = ""
    if not content:
        return (False, "nothing to write (no recent answer)")
    target = os.path.expanduser(path)
    try:
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(target, "w") as f:
            f.write(content)
    except OSError as e:
        return (False, f"could not write {target}: {e}")
    n = content.count("\n") + (0 if content.endswith("\n") else 1)
    return (True, f"wrote {n} lines → {target}")
