"""Model inference orchestration. mlx_lm is imported lazily so mocked
tests never touch it."""

from dwim.prompt import build_messages, sanitize

_MODEL_CACHE: dict = {}


def load_model(model_name: str):
    from mlx_lm import load  # lazy: only when actually running the model
    if model_name not in _MODEL_CACHE:
        _MODEL_CACHE[model_name] = load(model_name)
    return _MODEL_CACHE[model_name]


def suggest(cmd, exit_code, model_name, *, generate_fn=None, load_fn=None):
    messages = build_messages(cmd, exit_code)
    load_fn = load_fn or load_model
    model, tokenizer = load_fn(model_name)
    prompt = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=False
    )
    if generate_fn is None:
        from mlx_lm import generate as generate_fn  # lazy
    raw = generate_fn(model, tokenizer, prompt=prompt, max_tokens=64, verbose=False)
    return sanitize(raw, cmd)
