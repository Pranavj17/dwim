import os
from dwim.context import gather


def test_gather_has_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ctx = gather()
    assert ctx["cwd"] == str(tmp_path)
    assert "git" in ctx and "last_cmd" in ctx


def test_gather_respects_xdg_cache_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    d = tmp_path / "dwim"
    d.mkdir()
    (d / "last").write_text("127\nbrw install\n")
    monkeypatch.chdir(tmp_path)
    ctx = gather()
    assert ctx["last_exit"] == "127"
    assert "brw install" in ctx["last_cmd"]
