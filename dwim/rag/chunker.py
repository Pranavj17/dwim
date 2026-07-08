"""Split a file into overlapping line-window chunks, recording 1-based inclusive
[start,end] line ranges so retrieval can cite file:line."""

_WINDOW = 40
_OVERLAP = 10
_MAX_CHARS = 2000


def chunk_text(text):
    lines = text.split("\n")
    n = len(lines)
    step = _WINDOW - _OVERLAP
    out = []
    i = 0
    while i < n:
        body = "\n".join(lines[i:i + _WINDOW]).strip()
        if body:
            out.append({"start": i + 1, "end": min(i + _WINDOW, n),
                        "text": body[:_MAX_CHARS]})
        if i + _WINDOW >= n:
            break
        i += step
    return out
