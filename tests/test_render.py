from dwim.render import render
from dwim.highlight import strip_ansi


def test_table_aligns_columns():
    md = "| Time | Mon |\n|------|-----|\n| 8:00 | Standup |\n| 9:00 | Dev |"
    out = render(md, 80)
    lines = out.split("\n")
    # header, separator, 2 body rows
    assert len(lines) == 4
    assert "─" in lines[1]                      # dim underline row
    assert "Standup" in strip_ansi(out) and "9:00" in strip_ansi(out)
    # columns aligned: 'Mon' header and 'Standup'/'Dev' start at same visual col
    plain = [strip_ansi(l) for l in lines]
    col = plain[0].index("Mon")
    assert plain[2][col:col+3] == "Sta" and plain[3][col:col+3] == "Dev"


def test_table_truncates_to_width():
    md = ("| A | B |\n|---|---|\n"
          "| " + "x" * 60 + " | " + "y" * 60 + " |")
    out = render(md, 40)
    for l in out.split("\n"):
        assert len(strip_ansi(l)) <= 40
    assert "…" in strip_ansi(out)


def test_malformed_table_falls_back_to_raw():
    md = "| A | B |\nnot-a-separator\n| 1 | 2 |"
    out = render(md, 80)
    assert out == md                            # unchanged: no separator row


def test_shell_code_block_highlighted_fence_gone():
    md = "```bash\nls -la | grep foo\n```"
    out = render(md, 80)
    assert "```" not in out
    assert "\033[" in out                       # ANSI present (highlighted)
    assert "ls -la | grep foo" in strip_ansi(out)


def test_non_shell_code_block_dimmed_not_shell_highlighted():
    md = "```js\nconst x = 1\n```"
    out = render(md, 80)
    assert "```" not in out
    assert "const x = 1" in strip_ansi(out)
    assert "\033[38;5;244m" in out              # dim, not the teal command color


def test_heading_bold_no_hashes():
    out = render("## Hello", 80)
    assert out.startswith("\033[1m")
    assert "#" not in strip_ansi(out)
    assert strip_ansi(out) == "Hello"


def test_lists_bulleted_and_numbered():
    assert strip_ansi(render("- apple", 80)) == "• apple"
    assert strip_ansi(render("1. first", 80)) == "1. first"


def test_inline_bold_and_code():
    out = render("a **b** `c`", 80)
    assert "\033[1m" in out                      # bold for **b**
    assert "\033[38;5;79m" in out                # teal for `c`
    assert strip_ansi(out) == "a b c"


def test_plain_text_passthrough():
    assert render("just some prose here", 80) == "just some prose here"


def test_never_raises():
    for bad in ["", "|broken|\n|", "```\nunclosed", "| a |\n|--|\n| ragged | x | y |"]:
        r = render(bad, 80)
        assert isinstance(r, str)


def test_many_column_table_falls_back_to_raw_within_width():
    # 12 columns can't align in width=40 even at the 3-char floor → keep raw,
    # so no rendered line silently overflows the terminal width.
    header = "| " + " | ".join(f"c{i}" for i in range(12)) + " |"
    sep = "|" + "|".join("---" for _ in range(12)) + "|"
    body = "| " + " | ".join(str(i) for i in range(12)) + " |"
    md = f"{header}\n{sep}\n{body}"
    out = render(md, 40)
    assert out == md                     # unchanged (raw), not a wrapped mess


def test_non_word_lang_fence_still_recognized():
    out = render("```c++\nint main(){}\n```\nDone.", 80)
    from dwim.highlight import strip_ansi
    assert "```" not in out
    assert "int main(){}" in strip_ansi(out)
    assert strip_ansi(out).rstrip().endswith("Done.")   # trailing prose not eaten


def test_escaped_pipe_in_cell_preserved():
    from dwim.highlight import strip_ansi
    md = "| A | B |\n|---|---|\n| x \\| y | z |"
    out = render(md, 80)
    assert "x | y" in strip_ansi(out)     # \| became a literal | inside the cell


def test_heading_with_inline_bold_stays_bold_throughout():
    out = render("## Deploy **now** carefully", 80)
    # after the inner **now** span, boldness is reopened, so the line never
    # drops to a bare reset mid-heading
    assert "\033[0m\033[1m" in out        # reset-then-reopen-bold marker
    assert not out.rstrip().endswith("carefully")  # (ends with _RESET, not raw)


def test_render_non_string_returns_string():
    assert render(123, 80) == ""
    assert render(None, 80) == ""
