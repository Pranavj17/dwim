"""CLI: dwim-engine --cmd "<command>" --exit <code>. Prints corrected
command to stdout (exit 0), nothing on no-suggestion (exit 1), or a Nix-setup
hint to stderr if mlx_lm is unavailable (exit 3)."""

import argparse
import os
import sys

from dwim.config import load_config


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="dwim-engine")
    parser.add_argument("--cmd", required=True)
    parser.add_argument("--exit", dest="exit_code", type=int, required=True)
    args = parser.parse_args(argv)

    fake = os.environ.get("DWIM_FAKE_SUGGESTION")
    if fake is not None:
        result = fake.strip() or None
    else:
        from dwim.engine import suggest
        cfg = load_config()
        try:
            result = suggest(args.cmd, args.exit_code, cfg["model"])
        except ImportError:
            print(
                "dwim: mlx_lm not available — add mlx-lm to your Nix "
                "home.packages and run `make switch`.",
                file=sys.stderr,
            )
            return 3

    if result:
        print(result)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
