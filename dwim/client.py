"""Client for the warm dwim-daemon. Returns a correction instantly if the
daemon is up; signals absence so callers can decide whether to load inline."""

import os
import socket

from dwim.daemon import SOCKET_PATH


class DaemonUnavailable(Exception):
    """No daemon is listening (socket missing or connection failed)."""


def ping(*, socket_path: str = SOCKET_PATH, timeout: float = 2.0) -> bool:
    """True if a warm daemon answers on the socket."""
    if not os.path.exists(socket_path):
        return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(socket_path)
        s.sendall(b"PING\n")
        resp = s.recv(64).decode(errors="replace").strip()
        s.close()
        return resp == "PONG"
    except OSError:
        return False


def query(cmd: str, exit_code: int, *, socket_path: str = SOCKET_PATH,
          timeout: float = 5.0) -> str:
    """Ask the daemon for a correction. Returns the suggestion (may be "").
    Raises DaemonUnavailable if the daemon isn't reachable."""
    if not os.path.exists(socket_path):
        raise DaemonUnavailable(socket_path)
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(socket_path)
        s.sendall(f"{exit_code}\t{cmd}\n".encode())
        resp = s.recv(65536).decode(errors="replace").strip("\n")
        s.close()
        return resp
    except OSError as e:
        raise DaemonUnavailable(str(e))
