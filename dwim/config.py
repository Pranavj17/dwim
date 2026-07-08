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


_RAG_DEFAULTS = {
    # No implicit corpus: `dwim index` with no path indexes nothing (indexing all
    # of ~/Documents is 30k+ files). Pass a dir, or set [rag] roots in config.toml.
    "roots": [],
    "exclude": [".git", "node_modules", ".venv", "venv", "env", "dist", "build",
                "_build", "deps", "target", "vendor", "Pods", "__pycache__",
                "site-packages", ".mypy_cache", ".pytest_cache", ".tox", ".next",
                ".cache", ".worktrees", ".idea", ".dart_tool", ".gradle",
                ".terraform", "DerivedData", "Carthage", "elm-stuff"],
    "extensions": [".md", ".txt", ".py", ".ex", ".exs", ".js", ".ts", ".rb",
                   ".go", ".rs", ".json", ".toml", ".yaml", ".yml", ".sh", ".zsh"],
    "max_file_kb": 1024,
    "model": "mlx-community/bge-small-en-v1.5-bf16",
}


def rag_config(path=None):
    path = path or os.path.join(_config_base(), "config.toml")
    data = {}
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = tomllib.load(f)
    rag = data.get("rag", {})
    out = {k: (list(v) if isinstance(v, list) else v)
           for k, v in _RAG_DEFAULTS.items()}
    for k, v in rag.items():
        if k in out:
            out[k] = v
    return out
