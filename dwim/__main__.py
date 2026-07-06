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
    parser.add_argument("--run", metavar="CMD",
                        help="classify CMD; run it captured (read-only, or mutating with --force); print JSON")
    parser.add_argument("--force", action="store_true",
                        help="with --run: permit executing a mutating command (user approved)")
    parser.add_argument("--repair", action="store_true",
                        help="read a JSON history array on stdin; print repair candidates")
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
        gray, reset, cyan = "\033[38;5;244m", "\033[0m", "\033[38;5;110m"
        print(f"{gray}⋯ dwim is thinking…{reset}", file=sys.stderr, flush=True)
        # The runner streams the agent's tool calls to stderr live (gray) as it
        # works; then we print the answer and the command candidates.
        result = run_action(args.action,
                            runner=lambda p, md: claude_run(p, md, effort),
                            context=gather(), model=model)
        if result["answer"]:
            print(f"{cyan}✦{reset} {result['answer']}", file=sys.stderr)
        for c in result["commands"]:
            # "<plain-English desc>\t<command>" — fzf shows the desc, previews
            # the command, and loads the command on select.
            print(f"{c['desc'] or c['cmd']}\t{c['cmd']}")
        return 0 if result["commands"] else 1

    if args.run is not None:
        import json
        import shutil
        from dwim.executor import (is_interactive, is_read_only, run_captured,
                                   first_binary)
        cmd = args.run
        interactive = is_interactive(cmd)
        read_only = is_read_only(cmd)
        # Execute ONLY when safe (read-only) or explicitly approved (mutating +
        # --force). Interactive commands are never run here.
        may_run = (not interactive) and (read_only or args.force)
        if may_run:
            out = {"cmd": cmd, "interactive": interactive, "read_only": read_only,
                   "ran": True, **run_captured(cmd)}
        elif interactive and shutil.which(first_binary(cmd)) is None:
            # Interactive tool that isn't installed → report as not-found so the
            # loop repairs it (offer an install) instead of handing off a dud.
            binv = first_binary(cmd)
            out = {"cmd": cmd, "interactive": True, "read_only": read_only,
                   "ran": False, "exit": 127, "stdout": "",
                   "stderr": f"zsh: command not found: {binv}", "timed_out": False}
        else:
            out = {"cmd": cmd, "interactive": interactive, "read_only": read_only,
                   "ran": False, "exit": None, "stdout": "", "stderr": "",
                   "timed_out": False}
        print(json.dumps(out))
        return 0

    if args.repair:
        import json
        from dwim.repair import repair
        from dwim.claude_runner import run as claude_run
        try:
            history = json.loads(sys.stdin.read() or "[]")
        except json.JSONDecodeError:
            history = []
        last = history[-1] if history else {}
        if not history:
            return 0   # nothing to repair — never escalate to Claude on empty input
        for c in repair(history, last, runner=claude_run):
            print(f"{c['desc'] or c['cmd']}\t{c['cmd']}")
        return 0

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
