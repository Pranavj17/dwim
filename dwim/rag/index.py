"""Walk config roots and maintain the RAG index incrementally: re-embed only the
files whose content changed since the last build; drop chunks of deleted files."""

import hashlib
import os

import numpy as np

from dwim.rag import store
from dwim.rag.chunker import chunk_text
from dwim.rag.embed import embed_texts


def _sha1(text):
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


def _iter_files(roots, excludes, exts, max_kb):
    for root in roots:
        root = os.path.expanduser(root)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in excludes]
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() not in exts:
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    if os.path.getsize(p) > max_kb * 1024:
                        continue
                except OSError:
                    continue
                yield p


def build(roots, excludes, exts, max_kb, model, progress=None):
    """Build/update the index. `progress(done, total, added, chunks)` is called
    per file so a long run (indexing ~/Documents can be tens of thousands of
    files) shows live feedback instead of grinding silently."""
    vectors, chunks, manifest = store.load_index()
    prev_files = (manifest or {}).get("files", {})
    old_by_file = {}
    if vectors is not None and len(chunks) == len(vectors):
        for row, c in enumerate(chunks):
            old_by_file.setdefault(c["file"], []).append((c, vectors[row]))

    new_chunks, new_rows, new_files = [], [], {}
    added = skipped = 0
    files = list(_iter_files(roots, excludes, exts, max_kb))
    total = len(files)
    for i, p in enumerate(files):
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        h = _sha1(text)
        # Fast-path on an unchanged hash regardless of chunk count: a file that is
        # empty/all-blank produces 0 chunks (absent from old_by_file), so requiring
        # `p in old_by_file` re-read+re-chunked it every run. `.get(p, [])` reuses
        # its (possibly empty) chunks. old_by_file is only populated from a
        # length-consistent index, so this can't resurrect stale rows.
        if prev_files.get(p, {}).get("hash") == h:
            for c, v in old_by_file.get(p, []):
                new_chunks.append(c); new_rows.append(v)
            skipped += 1
        else:
            cks = chunk_text(text)
            if cks:
                vecs = embed_texts([c["text"] for c in cks], model)
                for c, v in zip(cks, vecs):
                    new_chunks.append({"file": p, "start": c["start"],
                                       "end": c["end"], "text": c["text"]})
                    new_rows.append(v)
            added += 1
        new_files[p] = {"mtime": os.path.getmtime(p), "hash": h}
        if progress:
            progress(i + 1, total, added, len(new_chunks))

    dim = 384
    if old_by_file:
        dim = int(next(iter(old_by_file.values()))[0][1].shape[0])
    new_vectors = (np.vstack(new_rows).astype("float32")
                   if new_rows else np.zeros((0, dim), "float32"))
    store.save_index(new_vectors, new_chunks,
                     {"model": model, "dim": int(new_vectors.shape[1] or dim),
                      "files": new_files})
    removed = len(set(prev_files) - set(new_files))
    return {"files": len(new_files), "chunks": len(new_chunks),
            "added": added, "skipped": skipped, "removed": removed}
