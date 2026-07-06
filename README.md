# dwim

**Do What I Mean** — a local-LLM shell command corrector for zsh on Apple Silicon.

You fumble a command, it fails, you type `dwim`, and the corrected command lands
on your prompt ready to run:

```
❯ brw install pip
zsh: command not found: brw
❯ dwim
🔮 brew install pip▉      # on your command line — Enter to run
```

It never re-runs your failed command and never auto-executes the fix — you
always confirm.

## How it works

Two parts:

- **Engine** (`dwim-engine`) — a small Python CLI that runs a local
  [MLX](https://github.com/ml-explore/mlx) model via `mlx_lm`. Given a command
  and its exit code, it prints the corrected command. Installed via Homebrew.
- **Shell glue** — zsh `preexec`/`precmd` hooks record your last command + exit
  code to `~/.cache/dwim/last`; the `dwim` function calls the engine and loads
  the suggestion onto your command line with `print -z`.

The engine deliberately runs under the **Nix-provided** `python3`
(`~/.nix-profile/bin/python3`) so `import mlx_lm` resolves against the Nix
package regardless of what else is on `PATH`.

## Requirements

- Apple Silicon Mac (MLX is Metal-backed).
- A python with **pip-installed** `mlx` + `mlx-lm` at `~/.venvs/dwim`
  (the pip wheel has the Metal/GPU backend; Nix's `mlx` is CPU-only):

  ```sh
  python3 -m venv ~/.venvs/dwim
  ~/.venvs/dwim/bin/pip install mlx-lm
  ```

  Override the path with `DWIM_PYTHON` if you keep it elsewhere.

## Install

```sh
brew install pranavj17/dwim/dwim
```

Then source the shell glue (`dwim.zsh`) from your zsh config — see
`dwim.zsh` in the dotfiles repo.

## Config

`~/.config/dwim/config.toml`:

```toml
model = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
```

Swap in any MLX chat model. Smaller = faster but worse corrections.

## Development

```sh
~/.nix-profile/bin/python3 -m pytest        # unit + glue-adjacent tests
DWIM_LIVE=1 ~/.nix-profile/bin/python3 -m pytest tests/test_smoke.py  # real model
tests/glue/test_state.zsh && tests/glue/test_dwim.zsh                 # zsh glue
```

`DWIM_FAKE_SUGGESTION` and `DWIM_PYTHON` are test-only env seams.
