import socket
import threading

import dwim.daemon as daemon
import dwim.engine as engine
from dwim.client import DaemonUnavailable, query


def test_handle_ping():
    assert daemon.handle("PING", "m") == "PONG"


def test_handle_correction(monkeypatch):
    monkeypatch.setattr(engine, "suggest", lambda cmd, code, model: "brew install pip")
    # daemon.handle imports suggest into its own namespace at call time
    monkeypatch.setattr(daemon, "suggest", lambda cmd, code, model: "brew install pip")
    assert daemon.handle("127\tbrw install pip", "m") == "brew install pip"


def test_handle_empty_command():
    assert daemon.handle("127\t", "m") == ""


def test_client_raises_when_no_socket(tmp_path):
    missing = str(tmp_path / "nope.sock")
    try:
        query("brw install pip", 127, socket_path=missing)
        assert False, "expected DaemonUnavailable"
    except DaemonUnavailable:
        pass


def test_client_roundtrip_against_a_fake_server():
    import os, tempfile
    # macOS caps AF_UNIX paths at ~104 chars, so keep it short (not tmp_path).
    sock_path = os.path.join(tempfile.gettempdir(), f"dwimt{os.getpid()}.sock")
    if os.path.exists(sock_path):
        os.unlink(sock_path)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(sock_path)
    srv.listen(1)

    def serve_once():
        conn, _ = srv.accept()
        req = conn.recv(4096).decode().strip("\n")
        # echo a fixed correction regardless of input
        assert req == "127\tbrw install pip"
        conn.sendall(b"brew install pip\n")
        conn.close()

    t = threading.Thread(target=serve_once)
    t.start()
    out = query("brw install pip", 127, socket_path=sock_path)
    t.join()
    srv.close()
    assert out == "brew install pip"
