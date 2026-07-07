"""Read-only local context handed to the Claude agent."""

import os
import subprocess
import time

INVENTORY_TTL = 6 * 3600                 # seconds; inventory older than this is refreshed
_DOCS = os.path.expanduser("~/Documents")


def _run(cmd) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=2).stdout.strip()
    except Exception:
        return ""


def _cache_dir() -> str:
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(cache, "dwim")


def _inventory_path() -> str:
    return os.path.join(_cache_dir(), "inventory")


def _format_inventory(raw: str) -> str:
    # raw lines are `<size>\t<path>` (from `du -sh`); show `<name> <size>`.
    out = []
    for line in raw.splitlines()[:15]:
        parts = line.split("\t")
        if len(parts) == 2 and parts[1].strip():
            out.append(f"{os.path.basename(parts[1].strip())} {parts[0].strip()}")
    return " · ".join(out)


def _default_trigger() -> None:
    # Refresh the inventory for the NEXT call without blocking this one.
    try:
        subprocess.Popen(
            ["nohup", "dwim-engine", "--refresh-inventory"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, start_new_session=True,
        )
    except Exception:
        pass


def _names_only() -> str:
    names = _run(["ls", "-1", _DOCS])
    return " · ".join(n for n in names.splitlines()[:15] if n)


def _read_inventory(trigger_refresh=_default_trigger) -> str:
    path = _inventory_path()
    if os.path.exists(path):
        fresh = (time.time() - os.path.getmtime(path)) < INVENTORY_TTL
        with open(path) as f:
            raw = f.read().strip()
        if not fresh:
            trigger_refresh()               # stale → refresh in background for next call
        formatted = _format_inventory(raw)
        # Honor an existing (fresh or already-triggered) cache: fall back to a
        # names-only view WITHOUT an extra trigger when the body is empty.
        return formatted if formatted else _names_only()
    # No cache at all: kick off a build and give a fast names-only map for now.
    trigger_refresh()
    return _names_only()


def refresh_inventory() -> int:
    try:
        res = subprocess.run(
            "du -sh " + _DOCS + "/* 2>/dev/null | sort -rh | head -15",
            shell=True, capture_output=True, text=True, timeout=60,
        )
    except Exception:
        return 1
    path = _inventory_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(res.stdout)
    os.replace(tmp, path)                    # atomic
    return 0


def gather() -> dict:
    cwd = os.getcwd()
    git = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    state = os.path.join(cache, "dwim", "last")
    last_cmd, last_exit = "", ""
    if os.path.exists(state):
        with open(state) as f:
            lines = f.read().splitlines()
        if lines:
            last_exit = lines[0]
            last_cmd = "\n".join(lines[1:])
    ls = _run(["ls", "-a"])[:800]
    return {"cwd": cwd, "git": git, "last_cmd": last_cmd,
            "last_exit": last_exit, "ls": ls,
            "roots": "~/Documents, ~", "inventory": _read_inventory()}
