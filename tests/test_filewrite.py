import os
import tempfile
from dwim import filewrite


def _isolate(monkeypatch):
    d = tempfile.mkdtemp()
    monkeypatch.setenv("XDG_CACHE_HOME", d)
    return d


def test_last_answer_path_honors_xdg(monkeypatch):
    d = _isolate(monkeypatch)
    assert filewrite.last_answer_path() == os.path.join(d, "dwim", "last_answer")


def test_store_then_write(monkeypatch):
    _isolate(monkeypatch)
    filewrite.store_answer("line1\nline2\n")
    out = os.path.join(tempfile.mkdtemp(), "sub", "out.txt")   # parent 'sub' missing on purpose
    ok, msg = filewrite.write_last_answer(out)
    assert ok is True
    assert "2 lines" in msg and out in msg
    with open(out) as f:
        assert f.read() == "line1\nline2\n"


def test_write_refuses_empty(monkeypatch):
    _isolate(monkeypatch)
    filewrite.store_answer("")            # empty answer
    out = os.path.join(tempfile.mkdtemp(), "out.txt")
    ok, msg = filewrite.write_last_answer(out)
    assert ok is False and "nothing to write" in msg
    assert not os.path.exists(out)        # no file created


def test_write_refuses_missing(monkeypatch):
    _isolate(monkeypatch)                 # never stored anything
    out = os.path.join(tempfile.mkdtemp(), "out.txt")
    ok, msg = filewrite.write_last_answer(out)
    assert ok is False and "nothing to write" in msg


def test_write_overwrites_existing(monkeypatch):
    _isolate(monkeypatch)
    filewrite.store_answer("new content\n")
    fd, out = tempfile.mkstemp()
    os.close(fd)
    with open(out, "w") as f:
        f.write("OLD")
    ok, _ = filewrite.write_last_answer(out)
    assert ok is True
    with open(out) as f:
        assert f.read() == "new content\n"


def test_write_expands_tilde(monkeypatch):
    _isolate(monkeypatch)
    home = tempfile.mkdtemp()
    monkeypatch.setenv("HOME", home)
    filewrite.store_answer("hi\n")
    ok, msg = filewrite.write_last_answer("~/nested/out.txt")
    assert ok is True
    assert os.path.exists(os.path.join(home, "nested", "out.txt"))
