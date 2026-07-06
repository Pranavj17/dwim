from dwim.prompt import build_messages, sanitize, SYSTEM_PROMPT


def test_build_messages_includes_command_and_system():
    msgs = build_messages("brw install pip", 127)
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == SYSTEM_PROMPT
    assert msgs[-1]["role"] == "user"
    assert "brw install pip" in msgs[-1]["content"]


def test_build_messages_127_says_not_found():
    msgs = build_messages("brw install pip", 127)
    assert "not found" in msgs[-1]["content"].lower()


def test_build_messages_other_exit_mentions_code():
    msgs = build_messages("git puhs", 1)
    assert "1" in msgs[-1]["content"]


def test_sanitize_strips_code_fences():
    assert sanitize("```\nbrew install pip\n```", "brw install pip") == "brew install pip"


def test_sanitize_takes_first_nonempty_line():
    assert sanitize("brew install pip\nThis fixes the typo.", "brw x") == "brew install pip"


def test_sanitize_strips_prompt_markers_and_quotes():
    assert sanitize('$ "brew install pip"', "brw") == "brew install pip"


def test_sanitize_strips_special_eos_tokens():
    assert sanitize("git status<|im_end|>", "gti status") == "git status"
    assert sanitize("ls -la</s>", "sl -la") == "ls -la"


def test_sanitize_returns_none_when_identical():
    assert sanitize("brew install pip", "brew install pip") is None


def test_sanitize_returns_none_when_empty():
    assert sanitize("   \n  ", "anything") is None
