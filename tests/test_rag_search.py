import numpy as np, dwim.rag.search as S
from dwim.rag import store

def test_search_returns_nearest(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    # 3 unit vectors; query closest to row 1
    vecs = np.array([[1,0,0],[0,1,0],[0,0,1]], "float32")
    chunks = [{"file":"a","start":1,"end":2,"text":"A"},
              {"file":"b","start":1,"end":2,"text":"B"},
              {"file":"c","start":1,"end":2,"text":"C"}]
    store.save_index(vecs, chunks, {"model":"m","dim":3,"files":{}})
    monkeypatch.setattr(S, "embed_texts", lambda q, m=None: np.array([[0,1,0]], "float32"))
    hits = S.search("q", k=2)
    assert hits[0]["file"] == "b" and len(hits) == 2

def test_search_missing_index_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "empty"))
    assert S.search("q") == []
