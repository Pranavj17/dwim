"""Decide whether an @ input is a TASK (offer the agentic loop) or a QUESTION
(answer read-only). Deterministic, local, zero cost. The result only OFFERS the
loop, so a misclassification costs one keystroke and defaults to the safe
(non-mutating) question path."""

# Leading interrogatives → question. Checked first so "do you know…" is a
# question while "do the migration" (imperative "do") still falls to task only
# via the verb list below (which omits bare "do" to avoid the collision).
_QUESTION_LEADERS = {
    "how", "what", "why", "where", "when", "who", "which", "does", "do", "did",
    "can", "could", "is", "are", "was", "were", "should", "would", "will",
    "explain", "show", "tell", "describe",
}

_TASK_VERBS = {
    "fix", "add", "make", "rename", "bump", "create", "refactor", "delete",
    "move", "run", "write", "update", "remove", "implement", "build", "install",
    "generate", "replace", "extract", "rewrite", "format", "sort", "commit",
    "revert", "apply", "set", "change", "enable", "disable", "wire", "hook",
}


def classify(text: str) -> str:
    first = (text or "").strip().lower().split(None, 1)
    if not first:
        return "question"
    head = first[0].rstrip(",:")
    if head in _QUESTION_LEADERS:
        return "question"
    if head in _TASK_VERBS:
        return "task"
    return "question"
