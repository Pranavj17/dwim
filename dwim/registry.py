"""Static multi-model registry: ~/.config/dwim/config.toml maps roles→models."""

import os
import shutil
import subprocess
import tomllib

DEFAULT_CONFIG = os.path.expanduser("~/.config/dwim/config.toml")

_DEFAULTS = [
    {"name": "qwen", "backend": "mlx",
     "model": "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit",
     "role": "correct", "effort": ""},
    {"name": "haiku", "backend": "claude-cli", "model": "haiku",
     "role": "action", "effort": "low"},
    {"name": "sonnet", "backend": "claude-cli", "model": "sonnet",
     "role": "action_deep", "effort": ""},
]


def load_models(path=None) -> list[dict]:
    path = path or DEFAULT_CONFIG
    if not os.path.exists(path):
        return [dict(m) for m in _DEFAULTS]
    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            import sys
            print(f"dwim: ignoring malformed {path}: {e}", file=sys.stderr)
            return [dict(m) for m in _DEFAULTS]
    out = []
    for name, m in data.get("models", {}).items():
        out.append({
            "name": name,
            "backend": m.get("backend", ""),
            "model": m.get("model", ""),
            "role": m.get("role", ""),
            "effort": m.get("effort", ""),   # claude effort level (low/medium/high)
        })
    return out or [dict(m) for m in _DEFAULTS]


def resolve_role(role: str, path=None) -> dict | None:
    for m in load_models(path):
        if m["role"] == role:
            return m
    return None


def backend_status(m: dict) -> str:
    backend = m.get("backend", "")
    if backend == "claude-cli":
        return "connected" if shutil.which("claude") else "offline"
    if backend == "mlx":
        py = os.path.expanduser("~/.venvs/dwim/bin/python")
        if not os.path.exists(py):
            return "offline"
        # find_spec locates the package without importing it — mlx_lm's real
        # import is ~5s and raced the old timeout. Keep the probe light + static.
        probe = ("import importlib.util, sys; "
                 "sys.exit(0 if importlib.util.find_spec('mlx_lm') else 1)")
        try:
            r = subprocess.run([py, "-c", probe], capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:
            return "offline"
        return "connected" if r.returncode == 0 else "offline"
    if backend == "ollama":
        return "connected" if shutil.which("ollama") else "offline"
    return "unknown"
