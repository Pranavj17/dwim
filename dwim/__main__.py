"""CLI: dwim-engine --cmd "<command>" --exit <code>. Prints corrected
command to stdout (exit 0), nothing on no-suggestion (exit 1), a Nix-setup
hint if mlx_lm is unavailable (exit 3), or exit 4 with --daemon-only when the
warm daemon isn't running (caller should not block on an inline load)."""

import argparse
import os
import sys

from dwim.config import load_config


def _term_width() -> int:
    import shutil
    try:
        return int(os.environ.get("COLUMNS") or
                   shutil.get_terminal_size((80, 24)).columns)
    except (ValueError, OSError):
        return 80


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
    parser.add_argument("--refresh-inventory", action="store_true",
                        help="recompute the ~/Documents size inventory cache, then exit")
    parser.add_argument("--models", action="store_true",
                        help="list configured models + role + status")
    parser.add_argument("--action", metavar="INTENT",
                        help="run the Claude agent palette for INTENT")
    parser.add_argument("--personas", action="store_true",
                        help="list configured @ personas + their dir, then exit")
    parser.add_argument("--tier", choices=["fast", "deep"], default="fast",
                        help="with --action: 'deep' uses the action_deep model (e.g. sonnet)")
    parser.add_argument("--run", metavar="CMD",
                        help="classify CMD; run it captured (read-only, or mutating with --force); print JSON")
    parser.add_argument("--force", action="store_true",
                        help="with --run: permit executing a mutating command (user approved)")
    parser.add_argument("--repair", action="store_true",
                        help="read a JSON history array on stdin; print repair candidates")
    parser.add_argument("--write", metavar="PATH",
                        help="write the last @ answer (cache) to PATH; exit 1 if none")
    parser.add_argument("--index", nargs="*", metavar="PATH",
                        help="build/update the RAG index (default: config roots)")
    parser.add_argument("--rag", metavar="QUERY",
                        help="semantic-search the RAG index; print file:line hits")
    parser.add_argument("--k", type=int, default=5, help="with --rag: number of hits")
    parser.add_argument("--classify", metavar="TEXT",
                        help="print whether TEXT is a 'task' or 'question', then exit")
    parser.add_argument("--plan", metavar="TEXT",
                        help="form a read-only plan for TEXT; render it + persist for --do")
    parser.add_argument("--do", action="store_true",
                        help="execute the approved plan at --plan-file")
    parser.add_argument("--plan-file", metavar="PATH",
                        help="with --do: path to the persisted approved-plan JSON")
    parser.add_argument("--confine-hook", action="store_true",
                        help="PreToolUse hook: deny edits/commands outside the approved plan")
    args = parser.parse_args(argv)

    if args.confine_hook:
        from dwim.agent.confine_hook import main as hook_main
        return hook_main()

    if args.classify is not None:
        from dwim.classify import classify
        print(classify(args.classify))
        return 0

    if args.plan is not None:
        import json
        from dwim.agent.planner import make_plan
        from dwim.agent.plan_render import render_plan
        from dwim.config import agent_config
        cfg = agent_config()
        plan = make_plan(args.plan, cfg["model"], cfg["timeout"])
        if plan is None:
            print("dwim: couldn't form a plan — try rephrasing, or ask read-only with @.",
                  file=sys.stderr)
            return 1
        print(render_plan(plan))
        cache = os.path.join(os.environ.get("XDG_CACHE_HOME",
                             os.path.expanduser("~/.cache")), "dwim", "agent")
        os.makedirs(cache, exist_ok=True)
        pf = os.path.join(cache, "pending_plan.json")
        # Persist the full task + steps (not just files/commands) so --do can
        # rebuild the Plan and hand the execute agent the step detail it needs.
        with open(pf, "w") as f:
            json.dump({"task": args.plan, "steps": plan.steps,
                       "files": sorted(plan.files()), "commands": plan.commands()}, f)
        print(f"DWIM_PLAN_READY {pf}")
        return 0

    if args.do:
        import json
        import subprocess
        from dwim.agent.execute import execute
        from dwim.agent.plan import Plan
        from dwim.config import agent_config
        root = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True).stdout.strip() or os.getcwd()
        with open(args.plan_file) as f:
            raw = json.load(f)
        plan = Plan(raw.get("steps", []))
        out = execute(plan, root, agent_config(), task=raw.get("task", ""))
        print(out["report"])
        if out["snapshot"]:
            print(f"\n· rollback: git stash apply {out['snapshot']}", file=sys.stderr)
        return 0

    if args.status:
        return _print_status()

    if args.refresh_inventory:
        from dwim.context import refresh_inventory
        return refresh_inventory()

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

    if args.personas:
        from dwim.persona import list_personas, personas_dir
        for name in list_personas():
            print(name)
        print(f"\npersonas dir: {personas_dir()}  "
              "(use as `@<name> intent`, e.g. `@git undo my last commit`)")
        return 0

    if args.write:
        from dwim.filewrite import write_last_answer
        ok, msg = write_last_answer(args.write)
        print(msg, file=sys.stderr)
        return 0 if ok else 1

    if args.action is not None:
        from dwim.action import run_action
        from dwim.context import gather
        from dwim.claude_runner import run as claude_run
        from dwim.persona import resolve_persona, load_persona, ensure_starters
        from dwim.registry import resolve_role
        # Seed the shipped starter personas (git/k8s/sql) on first use so `@git`
        # works out of the box — resolve_persona is side-effect-free, so without
        # this a fresh install matches nothing until `dwim personas` is run once.
        ensure_starters()
        # A persona is selected by an EXACT word-1 match on the intent; otherwise
        # the whole line is the intent. Prompt-only: no tier/model change here.
        name, intent = resolve_persona(args.action)
        ptext = load_persona(name) if name else ""
        if name:
            os.environ["DWIM_PERSONA"] = name   # so the spinner can label it
        role = "action_deep" if args.tier == "deep" else "action"
        m = resolve_role(role) or resolve_role("action")
        model = m["model"] if m else ("sonnet" if args.tier == "deep" else "haiku")
        effort = (m.get("effort") if m else "") or ""
        gray, reset, cyan = "\033[38;5;244m", "\033[0m", "\033[38;5;110m"
        icon = os.environ.get("DWIM_ICON", "✨")
        # Record which model handled this @ run (so the shell panel can label it)
        # and show it live — makes @ (fast) vs @@ (deep) routing visible.
        _cache = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
        try:
            os.makedirs(os.path.join(_cache, "dwim"), exist_ok=True)
            with open(os.path.join(_cache, "dwim", "last_model"), "w") as _f:
                _f.write(model)
        except OSError:
            pass
        # The runner shows its own live spinner (the "thinking" indicator) that
        # collapses to a one-line breadcrumb; then we print the answer and the
        # command candidates. No separate "thinking…" line — the spinner is it.
        resume = os.environ.get("DWIM_RESUME", "")
        result = run_action(intent,
                            runner=lambda p, md: claude_run(p, md, effort, resume=resume),
                            context=gather(), model=model,
                            persona_text=ptext, persona_name=name or "")
        from dwim.filewrite import store_answer
        store_answer(result["answer"])   # so a later dwim-write can save it
        if result["answer"]:
            from dwim.render import render
            shown = render(result["answer"], _term_width())
            # multi-line render (a table/code block) prints BELOW the ✦ marker so
            # its column alignment isn't offset by the "✦ " prefix.
            sep = "\n" if "\n" in shown else " "
            print(f"{cyan}✦{reset}{sep}{shown}", file=sys.stderr)
        for c in result["commands"]:
            # "<plain-English desc>\t<command>" — fzf shows the desc, previews
            # the command, and loads the command on select.
            print(f"{c['desc'] or c['cmd']}\t{c['cmd']}")
        sid = result.get("session_id", "")
        target = os.environ.get("DWIM_SESSION_FILE") or \
            os.path.join(_cache, "dwim", "last_session")
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w") as _sf:
                _sf.write(sid)
        except OSError:
            pass
        # Success if we produced anything useful — commands OR an answer. An
        # answer-only result (a text/explain task) is a valid deliverable, not a
        # failure, so it must not exit non-zero (that reddens $? and breaks `&&`).
        return 0 if (result["commands"] or result["answer"]) else 1

    if args.run is not None:
        import json
        import shutil
        from dwim.executor import (is_interactive, is_read_only, run_captured,
                                   first_binary)
        from dwim.highlight import highlight
        cmd = args.run
        interactive = is_interactive(cmd)
        read_only = is_read_only(cmd)
        # Syntax-highlighted form for the shell to DISPLAY at the consent gate
        # and in the result panel — display-only, never executed (the shell runs
        # the raw `cmd`). Lossless: strip_ansi(cmd_hl) == cmd.
        cmd_hl = highlight(cmd)
        # Execute ONLY when safe (read-only) or explicitly approved (mutating +
        # --force). Interactive commands are never run here.
        may_run = (not interactive) and (read_only or args.force)
        if may_run:
            out = {"cmd": cmd, "cmd_hl": cmd_hl, "interactive": interactive,
                   "read_only": read_only, "ran": True, **run_captured(cmd)}
        elif interactive and shutil.which(first_binary(cmd)) is None:
            # Interactive tool that isn't installed → report as not-found so the
            # loop repairs it (offer an install) instead of handing off a dud.
            binv = first_binary(cmd)
            out = {"cmd": cmd, "cmd_hl": cmd_hl, "interactive": True,
                   "read_only": read_only, "ran": False, "exit": 127, "stdout": "",
                   "stderr": f"zsh: command not found: {binv}", "timed_out": False}
        else:
            out = {"cmd": cmd, "cmd_hl": cmd_hl, "interactive": interactive,
                   "read_only": read_only, "ran": False, "exit": None, "stdout": "",
                   "stderr": "", "timed_out": False}
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
        if not isinstance(history, list) or not history:
            return 0   # nothing to repair — never escalate to Claude on empty/garbage input
        last = history[-1]
        for c in repair(history, last, runner=lambda p, m: claude_run(p, m)[0]):
            print(f"{c['desc'] or c['cmd']}\t{c['cmd']}")
        return 0

    if args.index is not None:
        from dwim.config import rag_config
        from dwim.rag.index import build
        cfg = rag_config()
        roots = args.index or cfg["roots"]
        if not roots:
            print("dwim index: specify a directory, e.g. "
                  "`dwim index ~/Documents/helixa`\n"
                  "  (indexing all of ~/Documents is 30k+ files; set [rag] roots "
                  "in ~/.config/dwim/config.toml for a default)", file=sys.stderr)
            return 2

        def _prog(done, total, added, chunks):
            # live counter on ONE line (\r) so a long index (~/Documents can be
            # tens of thousands of files) is visibly working, not silent.
            if done == 1 or done % 25 == 0 or done == total:
                print(f"\r  indexing {done}/{total} files · {chunks} chunks "
                      f"({added} embedding)…", end="", file=sys.stderr, flush=True)

        s = build(roots, set(cfg["exclude"]), set(cfg["extensions"]),
                  cfg["max_file_kb"], cfg["model"], progress=_prog)
        print("", file=sys.stderr)   # end the \r progress line
        print(f"indexed {s['files']} files · {s['chunks']} chunks "
              f"({s['added']} changed, {s['skipped']} cached, {s['removed']} removed)",
              file=sys.stderr)
        return 0

    if args.rag is not None:
        from dwim.rag.search import search
        hits = search(args.rag, args.k)
        if not hits:
            print("· no RAG index yet — run `dwim index`", file=sys.stderr)
            return 1
        for h in hits:
            print(f"{h['file']}:{h['start']}-{h['end']}")
            for line in h["text"].splitlines():
                print(f"  {line}")
            print("---")
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
