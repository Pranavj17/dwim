"""Lossless ANSI syntax-highlighter for shell command strings.

The consent gate shows the user the exact command that is about to run, so
highlighting here is a SAFETY property, not just decoration: it may only ever
INSERT ANSI color escapes — never add, drop, reorder, or alter a single real
character (whitespace and quotes included). The invariant

    strip_ansi(highlight(cmd)) == cmd     for ALL inputs

must hold. The tokenizer covers the whole string span-by-span (whitespace and
unmatched text become plain spans), and `highlight` self-verifies against the
invariant before returning — if anything is off, it falls back to the raw
string rather than risk showing the user something other than what runs.
"""

import re

# 256-color SGR codes, tuned to stay legible on a dark terminal.
_CMD = "\033[38;5;79m"     # command / binary — teal-cyan
_FLAG = "\033[38;5;179m"   # -flags — amber
_STR = "\033[38;5;114m"    # 'quoted' / "quoted" strings — green
_OP = "\033[38;5;244m"     # | || && ; & > >> < << — gray
_RESET = "\033[0m"

# Everything else (paths, args, whitespace, subshell parens) stays default.
_PLAIN = ""

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

# Characters that terminate a bare word (whitespace, operators, quotes, parens).
_WORD_STOP = set(" \t\n|;&<>()'\"")


def strip_ansi(s: str) -> str:
    """Remove ANSI SGR escapes (the ones `highlight` inserts)."""
    return _ANSI_RE.sub("", s)


def _tokenize(s: str):
    """Split `s` into (text, color) spans that concatenate back to `s`.

    `cmd_pos` tracks whether the next bare word sits in COMMAND position — true
    at the start and right after a pipe / ; / & / && / || / ( / newline, false
    after a redirect (the target is a filename, not a binary).
    """
    spans = []
    i, n = 0, len(s)
    cmd_pos = True
    while i < n:
        c = s[i]
        # Whitespace run (plain; never a command boundary except newline below).
        if c in " \t":
            j = i
            while j < n and s[j] in " \t":
                j += 1
            spans.append((s[i:j], _PLAIN))
            i = j
            continue
        if c == "\n":
            spans.append((c, _PLAIN))
            cmd_pos = True
            i += 1
            continue
        # Two-char operators before single-char ones.
        two = s[i:i + 2]
        if two in ("&&", "||", ">>", "<<"):
            spans.append((two, _OP))
            cmd_pos = two in ("&&", "||")   # chain → new command; here-doc/append → filename
            i += 2
            continue
        if c in "|;&":
            spans.append((c, _OP))
            cmd_pos = True
            i += 1
            continue
        if c in "<>":
            spans.append((c, _OP))
            cmd_pos = False                  # redirect target is a filename
            i += 1
            continue
        if c == "(":
            spans.append((c, _PLAIN))
            cmd_pos = True                   # subshell → next word is a command
            i += 1
            continue
        if c == ")":
            spans.append((c, _PLAIN))
            i += 1
            continue
        # Quoted string — to the matching quote, or end-of-string if unterminated
        # (color to the end, still lossless).
        if c == "'" or c == '"':
            j = i + 1
            while j < n and s[j] != c:
                j += 1
            if j < n:
                j += 1                       # include the closing quote
            spans.append((s[i:j], _STR))
            cmd_pos = False
            i = j
            continue
        # Bare word: command (in command position), flag (leading -), else plain.
        j = i
        while j < n and s[j] not in _WORD_STOP:
            j += 1
        word = s[i:j]
        if cmd_pos:
            color = _CMD
        elif word.startswith("-"):
            color = _FLAG
        else:
            color = _PLAIN
        spans.append((word, color))
        cmd_pos = False
        i = j
    return spans


def _wrap(text: str, color: str) -> str:
    if not color or not text:
        return text
    return color + text + _RESET


def highlight(cmd: str) -> str:
    """Return `cmd` with ANSI color added, preserving every real character.

    Self-verifies the lossless invariant and falls back to the raw string if it
    can't be guaranteed (e.g. pathological input) — highlighting must never
    change what the user sees relative to what runs.
    """
    try:
        result = "".join(_wrap(t, c) for t, c in _tokenize(cmd))
    except Exception:
        return cmd
    # Non-negotiable safety check: only return colored output when stripping the
    # color yields the original byte-for-byte.
    if strip_ansi(result) != cmd:
        return cmd
    return result
