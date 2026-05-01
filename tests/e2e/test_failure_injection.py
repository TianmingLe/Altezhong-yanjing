import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest
import websockets


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


class _SlowBackendHandler(BaseHTTPRequestHandler):
    delay_sec = 0.3

    def do_POST(self):
        _ = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        time.sleep(self.delay_sec)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *_):
        return


def _start_slow_backend(port: int):
    srv = HTTPServer(("127.0.0.1", port), _SlowBackendHandler)
    t = Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def _start_gateway(port: int, backend_port: int, tmp_path, max_items=10):
    log_path = tmp_path / "gateway.log"
    env = os.environ.copy()
    env["GATEWAY_HOST"] = "127.0.0.1"
    env["GATEWAY_PORT"] = str(port)
    env["BACKEND_BASE_URL"] = f"http://127.0.0.1:{backend_port}"
    env["GATEWAY_QUEUE_MAX_ITEMS"] = str(max_items)
    env["GATEWAY_QUEUE_MAX_BYTES"] = "4096"
    env["GATEWAY_DRAIN_TIMEOUT_SEC"] = "0.2"
    p = subprocess.Popen(
        [sys.executable, "docker/ble-gateway/gateway.py"],
        cwd=str(tmp_path.parent.parent),
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
    )
    t0 = time.time()
    while time.time() - t0 < 5.0:
        if log_path.exists() and '"event": "ready"' in log_path.read_text():
            return p, log_path
        if p.poll() is not None:
            out = log_path.read_text() if log_path.exists() else ""
            raise AssertionError(f"gateway exited early rc={p.returncode}, out={out}")
        time.sleep(0.05)
    out = log_path.read_text() if log_path.exists() else ""
    raise AssertionError(f"gateway not ready, out={out}")


def test_gateway_drain_timeout_emits_event(tmp_path):
    backend_port = _free_port()
    backend = _start_slow_backend(backend_port)
    gw_port = _free_port()
    gw, log_path = _start_gateway(gw_port, backend_port, tmp_path, max_items=3)

    async def flood():
        async with websockets.connect(f"ws://127.0.0.1:{gw_port}") as ws:
            await ws.send(json.dumps({"kind": "meta", "trace_id": "t-drain"}))
            for _ in range(30):
                await ws.send(json.dumps({"kind": "audio", "payload_b64": "AA==", "session_id": "s1"}))

    try:
        asyncio.run(flood())
        gw.terminate()
        gw.wait(timeout=10)
        out = log_path.read_text()
        assert '"event": "draining_timeout"' in out
        assert '"event": "gateway_shutdown"' in out
    finally:
        backend.shutdown()
        if gw.poll() is None:
            gw.kill()


@pytest.mark.skipif(os.environ.get("COMPOSE_MODE") != "1", reason="compose only")
def test_redis_flaky_does_not_block_and_logs_warning():
    backend = os.environ.get("BACKEND_BASE_URL", "http://backend:8000")
    gateway_ws = os.environ.get("GATEWAY_WS", "ws://ble-gateway:8787")

    env = os.environ.copy()
    env["BACKEND_BASE_URL"] = backend
    env["GATEWAY_WS"] = gateway_ws
    env["REDIS_URL"] = "redis://127.0.0.1:1/0"

    p = subprocess.run(
        [sys.executable, "scripts/mock_device.py", "--scenario", "normal", "--seed", "9", "--result-timeout-sec", "30"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert '"event": "done"' in p.stdout

