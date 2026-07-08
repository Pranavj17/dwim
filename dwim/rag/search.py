"""Semantic search over the local RAG index."""

import numpy as np

from dwim.rag import store
from dwim.rag.embed import DEFAULT, embed_texts


def search(query, k=5):
    vectors, chunks, manifest = store.load_index()
    # A torn index (a crash mid-`dwim index` leaves vectors.npy and chunks.jsonl
    # with different row counts) would make chunks[i] IndexError below. This tool
    # auto-runs for the agent, so degrade to [] instead of crashing — the next
    # `dwim index` rebuilds it.
    if vectors is None or len(chunks) == 0 or len(chunks) != len(vectors):
        return []
    model = (manifest or {}).get("model", DEFAULT)
    q = embed_texts([query], model)[0]
    scores = vectors @ q
    k = min(k, len(chunks))
    top = np.argsort(-scores)[:k]
    return [{"file": chunks[i]["file"], "start": chunks[i]["start"],
             "end": chunks[i]["end"], "text": chunks[i]["text"],
             "score": float(scores[i])} for i in top]
