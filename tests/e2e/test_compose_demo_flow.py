import json
import os
import subprocess
import sys
import time

import pytest


def _extract_trace_id(stdout: str) -> str:
    for line in stdout.splitlines():
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("event") == "start":
            return str(obj.get("trace_id"))
    raise AssertionError("trace_id_missing")


def _wait_healthz(url: str, timeout_sec: float = 30.0) -> None:
    import httpx

    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code == 200 and r.json().get("ok") is True:
                return
        except Exception:
            time.sleep(0.2)
    raise AssertionError("backend_not_ready")


@pytest.mark.skipif(os.environ.get("COMPOSE_MODE") != "1", reason="compose only")
def test_compose_demo_normal_resume_stress_and_redis_events():
    backend = os.environ.get("BACKEND_BASE_URL", "http://backend:8000")
    gateway_ws = os.environ.get("GATEWAY_WS", "ws://ble-gateway:8787")
    redis_url = os.environ.get("REDIS_URL")
    assert redis_url

    _wait_healthz(f"{backend}/healthz")

    env = os.environ.copy()
    env["BACKEND_BASE_URL"] = backend
    env["GATEWAY_WS"] = gateway_ws
    env["REDIS_URL"] = redis_url

    p = subprocess.run(
        [sys.executable, "scripts/mock_device.py", "--scenario", "normal", "--seed", "1", "--result-timeout-sec", "30"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert '"event": "done"' in p.stdout
    trace_id = _extract_trace_id(p.stdout)

    import redis.asyncio as redis
    import asyncio

    async def read_events():
        r = redis.from_url(redis_url, decode_responses=True)
        stream = f"demo:events:{trace_id}"
        resp = await r.xread({stream: "0-0"}, count=200, block=5000)
        await r.close()
        await r.connection_pool.disconnect()
        return resp

    events_resp = asyncio.run(read_events())
    assert events_resp
    payloads = []
    for _stream, items in events_resp:
        for _id, fields in items:
            if "payload" in fields:
                payloads.append(json.loads(fields["payload"]))
    assert any(e.get("op") == "session_init" for e in payloads)
    assert any(e.get("op") == "result" for e in payloads)

    p = subprocess.run(
        [sys.executable, "scripts/mock_device.py", "--scenario", "resume", "--seed", "2", "--result-timeout-sec", "30"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert '"event": "done"' in p.stdout
    trace_id = _extract_trace_id(p.stdout)

    async def read_resume_events():
        r = redis.from_url(redis_url, decode_responses=True)
        stream = f"demo:events:{trace_id}"
        resp = await r.xread({stream: "0-0"}, count=500, block=5000)
        await r.close()
        await r.connection_pool.disconnect()
        return resp

    resp = asyncio.run(read_resume_events())
    assert resp
    payloads = []
    for _stream, items in resp:
        for _id, fields in items:
            if "payload" in fields:
                payloads.append(json.loads(fields["payload"]))
    assert any(e.get("op") == "session_resume" for e in payloads)
    assert any(e.get("op") == "result" for e in payloads)

    p = subprocess.run(
        [sys.executable, "scripts/mock_device.py", "--scenario", "stress", "--seed", "3", "--stress-n", "80", "--send-timeout-sec", "0.2", "--result-timeout-sec", "30"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
        timeout=120,
    )
    assert '"event": "done"' in p.stdout
    assert "stress_progress" in p.stdout

