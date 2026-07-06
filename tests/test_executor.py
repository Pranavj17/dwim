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
