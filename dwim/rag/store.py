"""Read/write the RAG index files under ~/.cache/dwim/rag/."""

import json
import os

import numpy as np


def rag_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "dwim", "rag")


def _p(name):
    return os.path.join(rag_dir(), name)


def load_index():
    try:
        vectors = np.load(_p("vectors.npy"))
    except OSError:
        vectors = None
    chunks = []
    try:
        with open(_p("chunks.jsonl")) as f:
            chunks = [json.loads(x) for x in f if x.strip()]
    except OSError:
        pass
    manifest = {}
    try:
        with open(_p("manifest.json")) as f:
            manifest = json.load(f)
    except OSError:
        pass
    return vectors, chunks, manifest


def save_index(vectors, chunks, manifest):
    os.makedirs(rag_dir(), exist_ok=True)
    np.save(_p("vectors.npy"), vectors.astype("float32"))
    with open(_p("chunks.jsonl"), "w") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    with open(_p("manifest.json"), "w") as f:
        json.dump(manifest, f)
