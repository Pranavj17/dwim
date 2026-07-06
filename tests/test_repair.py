from dwim.repair import missing_binary, install_suggestion


def test_missing_binary_zsh():
    assert missing_binary("ncdu ~/x", "zsh: command not found: ncdu") == "ncdu"


def test_missing_binary_bash():
    assert missing_binary("htop", "bash: htop: command not found") == "htop"


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
