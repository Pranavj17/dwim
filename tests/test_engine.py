from dwim.engine import suggest


class FakeTokenizer:
    def apply_chat_template(self, messages, add_generation_prompt=False, tokenize=True):
        # Return the user content so the test can assert the cmd reached the model.
        return messages[-1]["content"]


def test_suggest_sanitizes_model_output():
    def fake_load(name):
        assert name == "some-model"
        return ("MODEL", FakeTokenizer())

    captured = {}

    def fake_generate(model, tokenizer, prompt, max_tokens, verbose):
        captured["prompt"] = prompt
        captured["model"] = model
        return "```\nbrew install pip\n```"

    out = suggest("brw install pip", 127, "some-model",
                  generate_fn=fake_generate, load_fn=fake_load)
    assert out == "brew install pip"
    assert "brw install pip" in captured["prompt"]
    assert captured["model"] == "MODEL"


def test_suggest_returns_none_when_model_echoes_input():
    def fake_load(name):
        return ("M", FakeTokenizer())

    def fake_generate(model, tokenizer, prompt, max_tokens, verbose):
        return "brw install pip"  # unchanged → no useful suggestion

    out = suggest("brw install pip", 127, "m",
                  generate_fn=fake_generate, load_fn=fake_load)
    assert out is None
