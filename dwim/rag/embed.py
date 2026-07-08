"""Local MLX text embeddings for dwim RAG. Loads a small bge model once per
process; returns L2-normalized float32 vectors so cosine == dot product."""

import numpy as np

DEFAULT = "mlx-community/bge-small-en-v1.5-bf16"
_DIM = 384
_MODEL = None
_TOK = None
_LOADED = None


def _load(model_name):
    global _MODEL, _TOK, _LOADED
    if _MODEL is None or _LOADED != model_name:
        from mlx_embeddings.utils import load
        _MODEL, _TOK = load(model_name)
        _LOADED = model_name
    return _MODEL, _TOK


def _one(model, tok, text):
    # truncate to the model's 512-token limit — a dense/minified chunk can exceed
    # it (verified: a 40-line chunk tokenized to 2002 tokens) and overflow bge's
    # position embeddings, which would abort the whole index build on one bad chunk.
    r = model(tok.encode(text or " ", return_tensors="mlx",
                         truncation=True, max_length=512))
    v = getattr(r, "text_embeds", None)
    if v is None:
        v = getattr(r, "pooler_output", None)
    if v is None:
        h = r.last_hidden_state if hasattr(r, "last_hidden_state") else r[0]
        v = h.mean(axis=1)
    return np.array(v, dtype=np.float32).reshape(-1)


def embed_texts(texts, model_name=DEFAULT):
    """(N, 384) float32, L2-normalized. Empty input -> (0, 384)."""
    if not texts:
        return np.zeros((0, _DIM), np.float32)
    model, tok = _load(model_name)
    vecs = np.vstack([_one(model, tok, t) for t in texts]).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (vecs / norms).astype(np.float32)
