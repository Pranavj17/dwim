"""Config loading for dwim. TOML at ~/.config/dwim/config.toml."""

import os
import tomllib

# 1.5B-Coder is the smallest model that reliably corrects real typos in
# benchmarking; the 0.5B echoes/garbles, Llama-1B hallucinates. Metal-backed.
DEFAULT_MODEL = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"


def _config_base() -> str:
    """XDG_CONFIG_HOME (else ~/.config) + /dwim — matches persona.py/registry.py."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "dwim")


def load_config(path: str | None = None) -> dict:
    path = path or os.path.join(_config_base(), "config.toml")
    if not os.path.exists(path):
        return {"model": DEFAULT_MODEL}
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return {"model": data.get("model", DEFAULT_MODEL)}
