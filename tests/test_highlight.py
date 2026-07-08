from dwim.highlight import highlight, strip_ansi

# The lossless invariant is a SAFETY property: highlighting may only insert ANSI
# color — never alter a real character. Cover plain commands, pipes, flags,
# single+double quotes, paths, operators, redirects, empty, and unterminated.
LOSSLESS_INPUTS = [
    "",
    "ls",
    "ls -la",
    "ls -la --color",
    "ps aux | head -20",
    'grep -r "foo bar" .',
    "find . -name '*.py'",
    "cat /etc/hosts",
    "du -sh ~/Documents/*",
    "a && b || c ; d",
    "echo hi > /tmp/x",
    "echo hi >> /tmp/x",
    "ls & echo done",
    "cat < input.txt",
    "sort file | uniq -c | sort -rh | head",
    'git commit -m "fix: a thing"',
    "echo 'a > b' | wc -l",
    'echo "oops',                # unterminated double quote
    "echo 'oops",                # unterminated single quote
    "(cd /tmp && ls)",
    "echo \t\t spaced   out \n next",
    "git worktree remove --force \"$w\"",
]


def test_lossless_invariant():
    for cmd in LOSSLESS_INPUTS:
        assert strip_ansi(highlight(cmd)) == cmd, repr(cmd)


def test_binary_is_colored():
    out = highlight("ls -la")
    assert out.startswith("\033[38;5;79m")   # command in teal-cyan
    assert "ls" in strip_ansi(out)


def test_flag_is_colored():
    out = highlight("ls -la")
    assert "\033[38;5;179m-la\033[0m" in out   # flag in amber, exact token


def test_quoted_string_is_colored():
    out = highlight('grep -r "foo bar" .')
    assert '\033[38;5;114m"foo bar"\033[0m' in out   # green, quotes preserved
    single = highlight("find . -name '*.py'")
    assert "\033[38;5;114m'*.py'\033[0m" in single


def test_operator_is_colored():
    out = highlight("ps aux | head")
    assert "\033[38;5;244m|\033[0m" in out   # gray pipe
    chained = highlight("a && b")
    assert "\033[38;5;244m&&\033[0m" in chained


def test_escape_appears_in_normal_command():
    assert "\033[" in highlight("ps aux | head -20")


def test_command_after_pipe_is_colored():
    # The word after a pipe is a fresh command → colored like a binary.
    out = highlight("ps aux | head -20")
    assert "\033[38;5;79mhead\033[0m" in out


def test_redirect_target_is_not_a_command():
    # The filename after `>` must NOT be colored as a command.
    out = highlight("echo hi > /tmp/x")
    assert "\033[38;5;79m/tmp/x" not in out
    assert "/tmp/x" in strip_ansi(out)


def test_strip_ansi_removes_all_escapes():
    colored = highlight('grep -r "foo bar" . | wc -l')
    plain = strip_ansi(colored)
    assert "\033[" not in plain
    assert plain == 'grep -r "foo bar" . | wc -l'


def test_empty_string():
    assert highlight("") == ""
    assert strip_ansi("") == ""


def test_unterminated_quote_is_lossless_and_colored():
    out = highlight('echo "oops')
    assert strip_ansi(out) == 'echo "oops'
    assert '\033[38;5;114m"oops\033[0m' in out   # colored to end, still lossless
