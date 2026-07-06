from dwim.action import build_prompt, parse_response, run_action


def test_build_prompt_includes_intent_and_context():
    p = build_prompt("find big files", {"cwd": "/tmp/x", "git": "main"})
    assert "find big files" in p
    assert "/tmp/x" in p


def test_parse_valid_json():
    out = parse_response('{"answer": "ok", "commands": ["ls -la", "du -sh *"]}')
    assert out["answer"] == "ok"
    assert out["commands"] == ["ls -la", "du -sh *"]


def test_parse_json_embedded_in_prose():
    raw = 'Here you go:\n{"answer":"hi","commands":["pwd"]}\nHope that helps.'
    out = parse_response(raw)
    assert out["commands"] == ["pwd"]


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
    assert out["commands"] == ["du -sh *"]
    assert "what is big" in captured["prompt"]
