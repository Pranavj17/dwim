import os
import time
from dwim.context import gather
from dwim import context


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


def test_read_inventory_cache_hit_no_refresh(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    d = tmp_path / "dwim"; d.mkdir()
    (d / "inventory").write_text("2.0G\t/Users/x/Documents/helixa\n725M\t/Users/x/Documents/xboard\n")
    calls = []
    out = context._read_inventory(lambda: calls.append(1))
    assert "helixa 2.0G" in out and "xboard 725M" in out
    assert calls == []                       # fresh file → no background refresh


def test_read_inventory_stale_triggers_refresh(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    d = tmp_path / "dwim"; d.mkdir()
    f = d / "inventory"; f.write_text("2.0G\t/Users/x/Documents/helixa\n")
    old = time.time() - (7 * 3600)
    import os as _os; _os.utime(f, (old, old))     # older than the 6h TTL
    calls = []
    out = context._read_inventory(lambda: calls.append(1))
    assert "helixa 2.0G" in out               # stale content still returned for THIS call
    assert calls == [1]                        # and a refresh was kicked off


def test_read_inventory_cold_names_only(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(context, "_DOCS", str(tmp_path / "Documents"))
    (tmp_path / "Documents").mkdir()
    (tmp_path / "Documents" / "alpha").mkdir()
    (tmp_path / "Documents" / "beta").mkdir()
    calls = []
    out = context._read_inventory(lambda: calls.append(1))
    assert "alpha" in out and "beta" in out    # names-only fallback
    assert calls == [1]                        # first build kicked off


def test_refresh_inventory_writes_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(context, "_DOCS", str(tmp_path / "Documents"))

    class _Res:
        stdout = "2.0G\t" + str(tmp_path / "Documents/helixa") + "\n"
    monkeypatch.setattr(context.subprocess, "run", lambda *a, **k: _Res())
    assert context.refresh_inventory() == 0
    cache = tmp_path / "dwim" / "inventory"
    assert cache.exists() and "helixa" in cache.read_text()


def test_gather_has_roots_and_inventory(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(context, "_DOCS", str(tmp_path / "Documents"))
    monkeypatch.setattr(context, "_default_trigger", lambda: None)
    (tmp_path / "Documents").mkdir()
    monkeypatch.chdir(tmp_path)
    ctx = gather()
    assert "roots" in ctx and "inventory" in ctx


def test_read_inventory_fresh_but_empty_does_not_trigger(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(context, "_DOCS", str(tmp_path / "Documents"))
    (tmp_path / "Documents").mkdir()
    d = tmp_path / "dwim"; d.mkdir()
    (d / "inventory").write_text("")          # fresh file, empty body
    calls = []
    context._read_inventory(lambda: calls.append(1))
    assert calls == []                         # fresh cache honored — no refresh


def test_read_inventory_stale_empty_triggers_once(tmp_path, monkeypatch):
    import os as _os
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(context, "_DOCS", str(tmp_path / "Documents"))
    (tmp_path / "Documents").mkdir()
    d = tmp_path / "dwim"; d.mkdir()
    f = d / "inventory"; f.write_text("")
    old = time.time() - (7 * 3600); _os.utime(f, (old, old))
    calls = []
    context._read_inventory(lambda: calls.append(1))
    assert calls == [1]                        # stale → exactly one trigger
