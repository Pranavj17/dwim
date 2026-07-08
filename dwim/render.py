"""Render an @ answer's markdown into clean terminal ANSI. DISPLAY ONLY — the
STORED answer (what dwim-write writes) stays raw; this only touches what prints.
Targeted: tables, fenced code, headings, lists, inline bold/code. Never raises —
any failure falls back to the raw text. No third-party deps."""

import re

from dwim.highlight import highlight as _sh_highlight

_BOLD = "\033[1m"
_DIM = "\033[38;5;244m"     # matches highlight._OP (gray)
_CODE = "\033[38;5;79m"     # inline `code` — teal, matches highlight._CMD
_RESET = "\033[0m"

_SHELL_LANGS = {"", "sh", "bash", "zsh", "shell", "console"}
_FENCE_RE = re.compile(r"^```(\w*)\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")
_H_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_UL_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
_OL_RE = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def render(text, width=80):
    """Markdown answer -> ANSI. Never raises: returns the raw text on any error."""
    try:
        return _render(text or "", width)
    except Exception:
        return text or ""


def _render(text, width):
    lines = text.split("\n")
    out = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        fence = _FENCE_RE.match(line.strip())
        if fence:
            lang = fence.group(1).lower()
            body, i = [], i + 1
            while i < n and not _FENCE_RE.match(lines[i].strip()):
                body.append(lines[i]); i += 1
            i += 1  # skip the closing fence (or run off the end if unclosed)
            out.append(_render_code(body, lang))
            continue
        if "|" in line and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]):
            block, j = [line, lines[i + 1]], i + 2
            while j < n and "|" in lines[j] and lines[j].strip():
                block.append(lines[j]); j += 1
            rendered = _render_table(block, width)
            if rendered is not None:
                out.append(rendered); i = j; continue
        out.append(_render_line(line)); i += 1
    return "\n".join(out)


def _render_code(body, lang):
    if lang in _SHELL_LANGS:
        rows = [_sh_highlight(b) for b in body]
    else:
        rows = [f"{_DIM}{b}{_RESET}" for b in body]
    return "\n".join("  " + r for r in rows)


def _cells(row):
    row = row.strip()
    if row.startswith("|"): row = row[1:]
    if row.endswith("|"): row = row[:-1]
    return [c.strip() for c in row.split("|")]


def _render_table(block, width):
    header = _cells(block[0])
    ncol = len(header)
    if ncol == 0:
        return None
    rows = []
    for r in block[2:]:
        c = _cells(r)
        if len(c) < ncol: c = c + [""] * (ncol - len(c))
        elif len(c) > ncol: c = c[:ncol]
        rows.append(c)
    widths = [len(header[k]) for k in range(ncol)]
    for r in rows:
        for k in range(ncol):
            widths[k] = max(widths[k], len(r[k]))
    gutter = 2
    total = sum(widths) + gutter * (ncol - 1)
    excess = total - width
    while excess > 0 and max(widths) > 3:          # shrink widest cols to fit
        m = widths.index(max(widths))
        widths[m] -= 1; excess -= 1

    def fit(cell, w):
        if len(cell) > w:
            cell = (cell[:w - 1] + "…") if w >= 1 else ""
        return cell.ljust(w)

    g = " " * gutter
    head = g.join(f"{_BOLD}{fit(header[k], widths[k])}{_RESET}" for k in range(ncol))
    sep = g.join(f"{_DIM}{'─' * widths[k]}{_RESET}" for k in range(ncol))
    out = [head, sep]
    for r in rows:
        out.append(g.join(fit(r[k], widths[k]) for k in range(ncol)))
    return "\n".join(out)


def _render_line(line):
    m = _H_RE.match(line)
    if m:
        return f"{_BOLD}{_render_inline(m.group(2))}{_RESET}"
    m = _UL_RE.match(line)
    if m:
        return f"{m.group(1)}• {_render_inline(m.group(2))}"
    m = _OL_RE.match(line)
    if m:
        return f"{m.group(1)}{m.group(2)}. {_render_inline(m.group(3))}"
    return _render_inline(line)


def _render_inline(text):
    text = _BOLD_RE.sub(lambda m: f"{_BOLD}{m.group(1)}{_RESET}", text)
    text = _INLINE_CODE_RE.sub(lambda m: f"{_CODE}{m.group(1)}{_RESET}", text)
    return text
