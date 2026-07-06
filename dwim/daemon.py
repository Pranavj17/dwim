"""Warm-model daemon. Loads the MLX model once and answers corrections over a
unix socket so `dwim` responds in <1s instead of reloading the model each call.

Wire protocol (newline-terminated, UTF-8) per connection:
  request:  "PING"                      -> response: "PONG"
  request:  "<exit_code>\\t<command>"    -> response: "<corrected command>" or ""
"""

import os
import socket
import sys

from dwim.config import load_config
from dwim.engine import load_model, suggest

SOCKET_PATH = os.path.expanduser("~/.cache/dwim/daemon.sock")


def handle(data: str, model_name: str) -> str:
    """Map one request line to its response line (no trailing newline)."""
    if data == "PING":
        return "PONG"
    code, _, cmd = data.partition("\t")
    if not cmd:
        return ""
    try:
        return suggest(cmd, int(code), model_name) or ""
    except Exception:
        return ""


def serve(socket_path: str = SOCKET_PATH) -> None:
    cfg = load_config()
    model_name = cfg["model"]
    load_model(model_name)  # warm the weights before accepting requests

    os.makedirs(os.path.dirname(socket_path), exist_ok=True)
    if os.path.exists(socket_path):
        os.unlink(socket_path)

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(socket_path)
    srv.listen(8)
    sys.stderr.write(f"dwim-daemon ready ({model_name}) on {socket_path}\n")
    sys.stderr.flush()

    while True:
        conn, _ = srv.accept()
        try:
            data = conn.recv(65536).decode(errors="replace").strip("\n")
            conn.sendall((handle(data, model_name) + "\n").encode())
        except Exception:
            pass
        finally:
            conn.close()


if __name__ == "__main__":
    serve()
