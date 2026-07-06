from dwim.action import build_prompt, parse_response, run_action


def test_build_prompt_includes_intent_and_context():
    p = build_prompt("find big files", {"cwd": "/tmp/x", "git": "main"})
    assert "find big files" in p
    assert "/tmp/x" in p


def test_parse_valid_json():
    out = parse_response('{"answer": "ok", "commands": ["ls -la", "du -sh *"]}')
    assert out["answer"] == "ok"
    assert [c["cmd"] for c in out["commands"]] == ["ls -la", "du -sh *"]


def test_parse_json_embedded_in_prose():
    raw = 'Here you go:\n{"answer":"hi","commands":["pwd"]}\nHope that helps.'
    out = parse_response(raw)
    assert [c["cmd"] for c in out["commands"]] == ["pwd"]


def test_parse_malformed_falls_back_to_answer():
    out = parse_response("just some text, no json")
    assert out["commands"] == []
    assert "just some text" in out["answer"]


def test_run_action_uses_injected_runner():
    captured = {}

    def fake_runner(prompt, model):
        captured["prompt"] = prompt
        return '{"answer":"found","commands":["du -sh *"]}'

    out = run_action("what is big", runner=fake_runner,
                     context={"cwd": "/tmp", "git": ""})
    assert [c["cmd"] for c in out["commands"]] == ["du -sh *"]
    assert "what is big" in captured["prompt"]


def test_parse_json_after_prose_with_earlier_brace():
    raw = ('While investigating I saw a config like {"foo": "bar"} in the repo. '
           'Here is my answer: {"answer": "use rg", "commands": ["rg TODO"]}')
    out = parse_response(raw)
    assert out["answer"] == "use rg"
    assert [c["cmd"] for c in out["commands"]] == ["rg TODO"]


def test_parse_non_list_commands_falls_back():
    out = parse_response('{"answer": "do this", "commands": "ls -la"}')
    assert out["commands"] == []          # not char-split
    assert "do this" in out["answer"]


def test_parse_brace_inside_json_string_value():
    out = parse_response('{"answer": "run {rg}", "commands": ["rg x"]}')
    assert [c["cmd"] for c in out["commands"]] == ["rg x"]  # brace inside a string value must not confuse the scanner


def test_run_action_passes_model_through():
    seen = {}
    def fake_runner(prompt, model):
        seen["model"] = model
        return '{"answer":"ok","commands":["pwd"]}'
    run_action("hi", runner=fake_runner, context={"cwd": "/tmp"}, model="sonnet")
    assert seen["model"] == "sonnet"


def test_parse_command_objects_carry_desc():
    out = parse_response('{"answer":"", "commands":[{"cmd":"ls -la","desc":"list files"}]}')
    assert out["commands"] == [{"cmd": "ls -la", "desc": "list files"}]


def test_parse_bare_string_commands_get_empty_desc():
    out = parse_response('{"answer":"", "commands":["pwd"]}')
    assert out["commands"] == [{"cmd": "pwd", "desc": ""}]
