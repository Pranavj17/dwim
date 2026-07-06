from dwim.executor import is_interactive, is_read_only


def test_interactive_detection():
    assert is_interactive("ncdu ~/Documents")
    assert is_interactive("htop")
    assert is_interactive("vim file.txt")
    assert not is_interactive("du -sh ~/Documents/*")
    assert not is_interactive("brew install ncdu")


def test_read_only_detection():
    assert is_read_only("du -sh ~/Documents/*")
    assert is_read_only("ls -la")
    assert is_read_only("git status")
    assert is_read_only("cat file.txt | grep foo")   # first verb governs
    assert not is_read_only("brew install ncdu")
    assert not is_read_only("rm -rf node_modules")
    assert not is_read_only("find . -delete")          # find is not on the read-only verb set


def test_empty_command_is_not_read_only():
    assert not is_read_only("")
    assert not is_interactive("")


def test_read_only_rejects_all_separators():
    for c in ["git status && git clean -fd", "du -sh ~ && rm -rf ~/x",
              "ls ; rm -rf x", "cat a || rm b", "ls & rm -rf x",
              "ls\nrm -rf x"]:
        assert not is_read_only(c), c


def test_read_only_rejects_redirects_and_substitution():
    for c in ["echo x > ~/.zshrc", "echo x >> ~/.zshrc", "echo x >&/tmp/evil",
              "grep $(whoami) file", "cat `id`", "cat <(rm x)",
              "echo x > /dev/nullx", "echo x > /dev/null.bak"]:
        assert not is_read_only(c), c


def test_read_only_rejects_double_quoted_substitution():
    for c in ['echo "$(touch /tmp/x)"', 'cat "$(rm x)"',
              'echo "`id`"', 'echo "${x:=$(rm x)}"']:
        assert not is_read_only(c), c


def test_read_only_rejects_backslash_quote_tricks():
    assert not is_read_only(r"echo \' ; touch /tmp/x")
    assert not is_read_only(r'echo \" ; rm x')


def test_read_only_rejects_subshell_and_unterminated():
    assert not is_read_only("(rm x)")
    assert not is_read_only("echo x; (rm y)")
    assert not is_read_only("ls 'unterminated")


def test_read_only_still_allows_variables_and_quoted_specials():
    assert is_read_only("du -sh $HOME")
    assert is_read_only('echo "hello world"')
    assert is_read_only("grep 'a > b' file")
    assert is_read_only("git log --pretty=format:'%h -> %s'")
    assert is_read_only(r'echo "\$(not real)"')   # escaped $ is literal, safe


def test_read_only_git_subcommands():
    assert is_read_only("git status")
    assert is_read_only("git log --oneline")
    assert is_read_only("git diff HEAD")
    assert not is_read_only("git branch -D main")
    assert not is_read_only("git show HEAD")   # dropped to mirror _ALLOWED


def test_read_only_allows_benign():
    for c in ["du -ah ~ 2>/dev/null | sort -rh | head -5",
              "cat f | grep x | wc -l", "ls -la", "df -h 2>/dev/null",
              "du -sh $HOME", "grep 'a > b' file", "grep 'foo(bar)' file",
              "git log --pretty=format:'%h -> %s'", "du 2>&1 | sort"]:
        assert is_read_only(c), c


def test_first_binary():
    from dwim.executor import first_binary
    assert first_binary("ncdu ~/Documents") == "ncdu"
    assert first_binary("du -sh ~/*") == "du"
    assert first_binary("") == ""


from dwim.executor import run_captured


def test_run_captured_success():
    r = run_captured("echo hello")
    assert r["exit"] == 0
    assert r["stdout"].strip() == "hello"
    assert r["timed_out"] is False


def test_run_captured_failure_has_stderr():
    r = run_captured("ls /no/such/path/xyz")
    assert r["exit"] != 0
    assert r["stderr"] != ""


def test_run_captured_command_not_found():
    r = run_captured("definitely-not-a-real-cmd-xyz")
    assert r["exit"] == 127


def test_run_captured_truncates_output():
    r = run_captured("printf 'x%.0s' {1..10000}", cap=100)
    assert len(r["stdout"]) <= 100


def test_run_captured_timeout():
    r = run_captured("sleep 5", timeout=1)
    assert r["timed_out"] is True
