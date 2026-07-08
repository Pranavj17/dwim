"""Personas — prompt-only domain experts for the `@` palette.

A persona is a system-prompt ADD-ON selected by the FIRST word after `@`
(`@git undo my last commit` → persona `git`, intent `undo my last commit`).
Personas customize ONLY the system prompt: no model/tier override, no tool or
allowlist changes, no stateful "active" persona. Detection is exact-match on
word-1 — a typo like `@gti …` is just a plain ask.

Persona files live in `<config_dir>/personas/<name>.md` and are plain markdown
appended below the base SYSTEM_PROMPT (which always governs).
"""

import os

# Starter personas written on first use. Content respects dwim's read-only
# ethos: prefer inspection, warn before anything destructive.
_STARTERS = {
    "git": (
        "# git persona\n\n"
        "Assisting with git.\n\n"
        "- Prefer safe, non-destructive commands; read state first "
        "(status, log, diff, branch).\n"
        "- Explain what a command does to history before suggesting it.\n"
        "- Warn clearly before rewriting PUBLISHED history (rebase, "
        "commit --amend on pushed commits, push --force). Prefer "
        "`--force-with-lease` over `--force`.\n"
        "- To act on ANOTHER repo or worktree, use `git -C <path> <command>` "
        "rather than cd'ing around.\n"
        "- Prefer reversible steps (a new branch, a stash) over destructive "
        "ones (`reset --hard`, `clean -fd`).\n"
    ),
    "k8s": (
        "# k8s persona\n\n"
        "Assisting with Kubernetes / kubectl.\n\n"
        "- Prefer read-only inspection: get, describe, logs, top, explain.\n"
        "- ALWAYS namespace-scope commands (`-n <namespace>`); never assume "
        "the default namespace.\n"
        "- Warn clearly before anything that mutates cluster state: delete, "
        "apply, edit, scale, `rollout restart`, patch, cordon/drain.\n"
        "- Confirm the current context "
        "(`kubectl config current-context`) before acting on prod.\n"
        "- Prefer `--dry-run=client -o yaml` to preview a change before "
        "applying it.\n"
    ),
    "sql": (
        "# sql persona\n\n"
        "Assisting with SQL and database CLIs.\n\n"
        "- Prefer read-only queries: SELECT, EXPLAIN, SHOW. Add a LIMIT when "
        "scanning a large table.\n"
        "- Warn clearly before any write or DDL: UPDATE, DELETE, INSERT, "
        "DROP, TRUNCATE, ALTER.\n"
        "- For a risky write, suggest wrapping it in a transaction "
        "(BEGIN … ROLLBACK/COMMIT) and testing the WHERE with a SELECT first.\n"
        "- Never suggest running a destructive statement against production "
        "without an explicit backup and confirmation.\n"
    ),
}


def _config_dir() -> str:
    """dwim's config dir, honoring XDG_CONFIG_HOME (else ~/.config). config.py and
    registry.py resolve the same way, so personas live beside config.toml."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "dwim")


def personas_dir() -> str:
    return os.path.join(_config_dir(), "personas")


def ensure_starters() -> None:
    """Create the personas dir (if missing) and seed the starter files.
    Idempotent — an existing file is NEVER overwritten, so user edits survive."""
    d = personas_dir()
    os.makedirs(d, exist_ok=True)
    for name, text in _STARTERS.items():
        path = os.path.join(d, f"{name}.md")
        if not os.path.exists(path):
            try:
                with open(path, "w") as f:
                    f.write(text)
            except OSError:
                pass


def list_personas() -> list[str]:
    """Sorted persona names (file stems). Seeds starters first so a fresh
    install is never empty."""
    ensure_starters()
    d = personas_dir()
    try:
        names = [f[:-3] for f in os.listdir(d) if f.endswith(".md")]
    except OSError:
        return []
    return sorted(names)


def resolve_persona(intent: str) -> tuple[str | None, str]:
    """Split `intent` into word-1 + remainder. If word-1 EXACTLY matches an
    existing `<name>.md` (case-sensitive), return (name, remainder.strip());
    otherwise (None, intent). Does NOT create files — detection must be a pure
    read, so ordinary asks don't seed the dir as a side effect."""
    parts = (intent or "").split(maxsplit=1)
    if not parts:
        return None, intent
    first = parts[0]
    d = personas_dir()
    # Case-SENSITIVE match: compare against the real directory listing rather
    # than os.path.exists, which is case-insensitive on macOS/APFS and would
    # let `@Git …` match git.md. No ensure_starters — detection is a pure read.
    try:
        stems = {f[:-3] for f in os.listdir(d) if f.endswith(".md")}
    except OSError:
        return None, intent
    if first in stems:
        remainder = parts[1].strip() if len(parts) > 1 else ""
        return first, remainder
    return None, intent


def load_persona(name: str) -> str:
    """Return the persona file's text, or "" if it doesn't exist."""
    path = os.path.join(personas_dir(), f"{name}.md")
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""
