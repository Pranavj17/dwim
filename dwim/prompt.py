"""Prompt construction and output sanitizing — pure, no model dependency."""

SYSTEM_PROMPT = (
    "You are a shell command corrector. Each user message is a shell command "
    "that failed, prefixed with its exit status in brackets. Reply with ONLY "
    "the corrected command on a single line — no explanation, no markdown, no "
    "code fences, no surrounding quotes. Fix misspelled command names, wrong "
    "flags, and obvious typos; keep the user's intent."
)

# Few-shot examples — tiny models need these to reliably correct typos rather
# than echo the input or truncate. Format matches the real final message.
_SHOTS = [
    ("[not found] git puhs origin main", "git push origin main"),
    ("[not found] brw install wget", "brew install wget"),
    ("[not found] pyhton script.py", "python script.py"),
    ("[exit 1] sl -la", "ls -la"),
]

_PROMPT_MARKERS = ("$ ", "❯ ", "> ", "# ")

# Chat models leak their end-of-turn markers into generated text; cut them off.
_EOS_MARKERS = ("<|", "</s>", "<end_of_turn>", "<eos>")


def _strip_eos(text: str) -> str:
    for marker in _EOS_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    return text


def _exit_tag(exit_code: int) -> str:
    return "not found" if exit_code == 127 else f"exit {exit_code}"


def build_messages(cmd: str, exit_code: int) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for user, assistant in _SHOTS:
        messages.append({"role": "user", "content": user})
        messages.append({"role": "assistant", "content": assistant})
    messages.append({"role": "user", "content": f"[{_exit_tag(exit_code)}] {cmd}"})
    return messages


def sanitize(raw: str, original: str) -> str | None:
    if not raw:
        return None
    # First real line, skipping blanks and code-fence markers (``` / ```bash).
    line = ""
    for ln in raw.splitlines():
        s = ln.strip()
        if not s or s.startswith("```"):
            continue
        line = s
        break
    line = _strip_eos(line).strip()
    line = line.strip("`").strip()
    for marker in _PROMPT_MARKERS:
        if line.startswith(marker):
            line = line[len(marker):]
            break
    if len(line) >= 2 and line[0] == line[-1] and line[0] in ("'", '"'):
        line = line[1:-1]
    line = line.strip()
    if not line or line == original.strip():
        return None
    return line
