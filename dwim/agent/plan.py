"""The structured plan produced by the read-only planning pass and shown at the
approval gate. `files()`/`commands()` define the approved set the confinement
hook enforces during execution."""

import json
import re
from dataclasses import dataclass

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


@dataclass
class Plan:
    steps: list

    def files(self):
        return {s["path"] for s in self.steps
                if s.get("kind") == "edit" and s.get("path")}

    def commands(self):
        return [s["command"] for s in self.steps
                if s.get("kind") == "run" and s.get("command")]


def _extract_json(raw):
    m = _FENCE.search(raw or "")
    return (m.group(1) if m else (raw or "")).strip()


def parse_plan(raw):
    try:
        data = json.loads(_extract_json(raw))
    except (ValueError, TypeError):
        return None
    steps = data.get("steps") if isinstance(data, dict) else None
    if not isinstance(steps, list):
        return None
    clean = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        kind = s.get("kind")
        if kind == "edit" and s.get("path"):
            clean.append({"kind": "edit", "path": s["path"],
                          "diff": s.get("diff"), "why": s.get("why", "")})
        elif kind == "run" and s.get("command"):
            clean.append({"kind": "run", "command": s["command"],
                          "why": s.get("why", "")})
    return Plan(clean) if clean else None
