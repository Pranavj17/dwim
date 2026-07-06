from dwim.repair import missing_binary, install_suggestion


def test_missing_binary_zsh():
    assert missing_binary("ncdu ~/x", "zsh: command not found: ncdu") == "ncdu"


def test_missing_binary_bash():
    assert missing_binary("htop", "bash: htop: command not found") == "htop"


def test_missing_binary_bare_no_shell_prefix():
    assert missing_binary("htop", "htop: command not found") == "htop"


def test_missing_binary_nonstandard_shell():
    assert missing_binary("ncdu", "fish: ncdu: command not found") == "ncdu"


def test_missing_binary_none_when_not_a_not_found_error():
    assert missing_binary("ls /x", "ls: /x: No such file or directory") is None


def test_install_suggestion_maps_known_tool():
    s = install_suggestion("ncdu", has_brew=True)
    assert s["cmd"] == "brew install ncdu"
    assert "ncdu" in s["desc"]


def test_install_suggestion_uses_formula_map():
    # fd's Homebrew formula is "fd" but bat's is "bat"; the map covers aliases.
    assert install_suggestion("fd", has_brew=True)["cmd"] == "brew install fd"


def test_install_suggestion_none_without_brew():
    assert install_suggestion("ncdu", has_brew=False) is None


from dwim.repair import repair


def test_repair_deterministic_not_found_skips_runner(monkeypatch):
    import dwim.repair as r
    monkeypatch.setattr(r.shutil, "which", lambda name: "/opt/homebrew/bin/brew")
    called = {"n": 0}

    def runner(prompt, model):
        called["n"] += 1
        return "{}"

    last = {"cmd": "ncdu ~/x", "exit": 127, "stdout": "",
            "stderr": "zsh: command not found: ncdu"}
    out = repair([last], last, runner=runner)
    assert out and out[0]["cmd"] == "brew install ncdu"
    assert called["n"] == 0   # deterministic path — no Claude call


def test_repair_falls_back_to_runner_for_other_failure():
    captured = {}

    def runner(prompt, model):
        captured["prompt"] = prompt
        return '{"answer":"try clean","commands":[{"cmd":"make clean","desc":"clean build"}]}'

    last = {"cmd": "make", "exit": 2, "stdout": "", "stderr": "build error: foo"}
    hist = [{"cmd": "make", "exit": 2, "stdout": "", "stderr": "build error: foo"}]
    out = repair(hist, last, runner=runner)
    assert out[0]["cmd"] == "make clean"
    assert "make" in captured["prompt"]        # history threaded in
    assert "build error: foo" in captured["prompt"]


def test_repair_returns_empty_when_runner_gives_nothing():
    last = {"cmd": "x", "exit": 1, "stdout": "", "stderr": "boom"}
    out = repair([last], last, runner=lambda p, m: '{"commands":[]}')
    assert out == []
