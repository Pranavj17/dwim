import os, numpy as np, dwim.rag.index as idx
from dwim.rag import store

def _fake_embed(texts, model_name=None):   # deterministic, no model load
    return np.array([[float(len(t)), 1.0] + [0.0]*382 for t in texts], np.float32)

def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(idx, "embed_texts", _fake_embed)

def test_build_indexes_and_is_incremental(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    root = tmp_path / "docs"; (root / "sub").mkdir(parents=True)
    (root / "a.md").write_text("\n".join(f"l{i}" for i in range(50)))
    (root / "sub" / "b.py").write_text("print(1)\nprint(2)\n")
    (root / "skip.bin").write_text("nope")            # wrong extension
    (root / ".git").mkdir(); (root / ".git" / "c.md").write_text("x")  # excluded dir
    s = idx.build([str(root)], {".git"}, {".md", ".py"}, 1024, "m")
    assert s["files"] == 2 and s["added"] == 2
    v, chunks, man = store.load_index()
    files = {c["file"] for c in chunks}
    assert any(f.endswith("a.md") for f in files)
    assert not any(".git" in f or f.endswith(".bin") for f in files)
    assert v.shape[0] == len(chunks)
    # rerun with no changes -> all cached, none re-added
    s2 = idx.build([str(root)], {".git"}, {".md", ".py"}, 1024, "m")
    assert s2["added"] == 0 and s2["skipped"] == 2
    # change one file -> only it re-added
    (root / "a.md").write_text("changed\n")
    s3 = idx.build([str(root)], {".git"}, {".md", ".py"}, 1024, "m")
    assert s3["added"] == 1 and s3["skipped"] == 1
    # delete a file -> removed from index
    os.remove(root / "sub" / "b.py")
    s4 = idx.build([str(root)], {".git"}, {".md", ".py"}, 1024, "m")
    assert not any(f.endswith("b.py") for f in {c["file"] for c in store.load_index()[1]})
