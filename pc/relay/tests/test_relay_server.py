import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import zlib

import websockets


def _crc32_u32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


async def _ws_roundtrip(uri: str, msg: dict) -> dict:
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps(msg))
        resp = await ws.recv()
        return json.loads(resp)


def _start_server(port: int) -> subprocess.Popen:
    env = os.environ.copy()
    cmd = [sys.executable, "relay_server.py", "--host", "127.0.0.1", "--port", str(port), "--demo"]
    return subprocess.Popen(cmd, cwd=os.path.dirname(__file__) + "/..", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)


def _wait_ready(p: subprocess.Popen, timeout_sec: float = 5.0) -> None:
    assert p.stdout is not None
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        line = p.stdout.readline()
        if not line:
            continue
        if "Server ready on ws://" in line:
            return
    raise AssertionError("server not ready")


def test_session_init_and_complete_returns_result():
    port = 18766
    p = _start_server(port)
    try:
        _wait_ready(p)
        uri = f"ws://127.0.0.1:{port}"

        resp = asyncio.run(_ws_roundtrip(uri, {"op": "session_init", "session_id": "s1", "frame_type": 2, "total_bytes": 16}))
        assert resp["op"] == "session_ack"
        assert resp["session_id"] == "s1"
        assert resp["accepted"] is True

        payload = b"\x01" * 16
        data_b64 = base64.b64encode(payload).decode("ascii")
        msg = {"op": "chunk", "session_id": "s1", "offset": 0, "data": data_b64, "crc32": _crc32_u32(payload)}

        async def run_flow():
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps(msg))
                ack = json.loads(await ws.recv())
                assert ack["op"] == "chunk_ack"
                assert ack["next_offset"] == 16

                await ws.send(json.dumps({"op": "session_complete", "session_id": "s1", "sha256": "0" * 64}))
                out = json.loads(await ws.recv())
                assert out["op"] == "result"
                assert out["session_id"] == "s1"
                assert out["result_type"] == "mock"

        asyncio.run(run_flow())
    finally:
        p.terminate()
        p.wait(timeout=5)

