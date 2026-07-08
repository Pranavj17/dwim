"""Render a Plan for the fzf approval gate. Display-only; never raises."""

_BOLD = "\033[1m"
_DIM = "\033[38;5;244m"
_GREEN = "\033[38;5;114m"
_RESET = "\033[0m"


def render_plan(plan, width=80):
    try:
        return _render(plan, width)
    except Exception:
        return "PLAN (unrenderable)\n"


def _render(plan, width):
    out = [f"{_BOLD}PLAN{_RESET}"]
    for i, s in enumerate(plan.steps, 1):
        if s.get("kind") == "edit":
            out.append(f"{i}. {_BOLD}edit{_RESET} {s.get('path','')}"
                       + (f"  {_DIM}— {s['why']}{_RESET}" if s.get("why") else ""))
            if s.get("diff"):
                for line in str(s["diff"]).splitlines():
                    c = _GREEN if line.startswith("+") else _DIM
                    out.append(f"     {c}{line}{_RESET}")
        else:
            out.append(f"{i}. {_BOLD}run{_RESET}  {s.get('command','')}"
                       + (f"  {_DIM}— {s['why']}{_RESET}" if s.get("why") else ""))
    return "\n".join(out) + "\n"
