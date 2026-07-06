"""CLI: dwim-engine --cmd "<command>" --exit <code>. Prints corrected
command to stdout (exit 0), nothing on no-suggestion (exit 1), a Nix-setup
hint if mlx_lm is unavailable (exit 3), or exit 4 with --daemon-only when the
warm daemon isn't running (caller should not block on an inline load)."""

import argparse
import os
import sys

from dwim.config import load_config


def _print_status() -> int:
    from dwim.client import ping
    cfg = load_config()
    warm = ping()
    device = "?"
    try:
        import mlx.core as mx
        device = str(mx.default_device())
    except Exception:
        pass
    print(f"model:   {cfg['model']}")
    print(f"daemon:  {'up (warm)' if warm else 'down (loads per call, ~6s)'}")
    print(f"device:  {device}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="dwim-engine")
    parser.add_argument("--cmd")
    parser.add_argument("--exit", dest="exit_code", type=int)
    parser.add_argument("--daemon-only", action="store_true",
                        help="use the warm daemon only; exit 4 if it's down")
    parser.add_argument("--status", action="store_true",
                        help="print the active model + daemon state, then exit")
    parser.add_argument("--models", action="store_true",
                        help="list configured models + role + status")
    parser.add_argument("--action", metavar="INTENT",
                        help="run the Claude agent palette for INTENT")
    args = parser.parse_args(argv)

    if args.status:
        return _print_status()

    if args.models:
        from dwim.registry import load_models, backend_status
        print(f"{'NAME':<10}{'BACKEND':<13}{'ROLE':<10}{'EFFORT':<8}{'STATUS'}")
        for m in load_models():
            st = backend_status(m)
            dot = "●" if st == "connected" else "○"
            eff = m.get("effort") or "—"
            print(f"{m['name']:<10}{m['backend']:<13}{m['role']:<10}{eff:<8}{dot} {st}")
        print("\ncustomize in ~/.config/dwim/config.toml — e.g.\n"
              "  [models.haiku]\n  backend = \"claude-cli\"\n  model = \"haiku\"\n"
              "  role = \"action\"\n  effort = \"low\"   # low|medium|high")
        return 0

    if args.action is not None:
        from dwim.action import run_action
        from dwim.context import gather
        from dwim.claude_runner import run as claude_run
        from dwim.registry import resolve_role
        m = resolve_role("action")
        model = m["model"] if m else "haiku"
        effort = (m.get("effort") if m else "low") or ""
        result = run_action(args.action,
                            runner=lambda p, md: claude_run(p, md, effort),
                            context=gather(), model=model)
        if result["answer"]:
            print(result["answer"], file=sys.stderr)   # inline note
        for c in result["commands"]:
            # "<plain-English desc>\t<command>" — fzf shows the desc, previews
            # the command, and loads the command on select.
            print(f"{c['desc'] or c['cmd']}\t{c['cmd']}")
        return 0 if result["commands"] else 1

    if not args.cmd or args.exit_code is None:
        parser.error("--cmd and --exit are required")

    fake = os.environ.get("DWIM_FAKE_SUGGESTION")
    if fake is not None:
        result = fake.strip() or None
    else:
        from dwim.client import DaemonUnavailable, query
        try:
            result = query(args.cmd, args.exit_code) or None
        except DaemonUnavailable:
            if args.daemon_only:
                return 4  # tell the shell to warm the daemon, don't block here
            # Inline fallback: load the model in-process (slow, ~6s).
            from dwim.engine import suggest
            cfg = load_config()
            try:
                result = suggest(args.cmd, args.exit_code, cfg["model"])
            except ImportError:
                print(
                    "dwim: mlx_lm not available — install it in ~/.venvs/dwim "
                    "(pip install mlx-lm).",
                    file=sys.stderr,
                )
                return 3

    if result:
        print(result)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
