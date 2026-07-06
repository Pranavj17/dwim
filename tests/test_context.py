import os
from dwim.context import gather


def test_gather_has_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ctx = gather()
    assert ctx["cwd"] == str(tmp_path)
    assert "git" in ctx and "last_cmd" in ctx
