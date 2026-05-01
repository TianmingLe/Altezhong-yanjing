import argparse
import asyncio
import base64
import json
import os
import random
import time
import uuid

import httpx
import websockets


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log_event(level: str, event: str, **fields):
    payload = {"ts": _ts(), "level": level, "service": "mock-device", "event": event}
    payload.update(fields)
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _rand_bytes(rng: random.Random, n: int) -> bytes:
    return bytes((rng.randrange(0, 256) for _ in range(n)))


async def _safe_send(ws, obj: dict, timeout_sec: float, max_retries: int, trace_id: str):
    raw = json.dumps(obj)
    attempt = 0
    while True:
        try:
            await asyncio.wait_for(ws.send(raw), timeout=timeout_sec)
            return True
        except Exception as e:
            attempt += 1
            log_event("warn", "send_retry", trace_id=trace_id, attempt=attempt, error=str(e))
            if attempt > max_retries:
                log_event("error", "send_drop", trace_id=trace_id)
                return False
            await asyncio.sleep(min(0.05 * (2**attempt), 0.5))


async def _poll_result(backend_base_url: str, trace_id: str, timeout_sec: float):
    async with httpx.AsyncClient(timeout=5.0) as client:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            r = await client.get(f"{backend_base_url}/demo/result/{trace_id}")
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "done":
                    return
            await asyncio.sleep(0.2)
    raise RuntimeError("timeout_waiting_for_result")


async def _get_missing_ranges(backend_base_url: str, session_id: str):
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"{backend_base_url}/demo/relay/state/{session_id}")
        if r.status_code != 200:
            return None
        data = r.json()
        missing = data.get("missing_ranges")
        if not isinstance(missing, list):
            return None
        return missing


async def _scenario_normal(ws, trace_id: str, session_id: str, feature: bytes, send_timeout_sec: float):
    await _safe_send(ws, {"kind": "meta", "trace_id": trace_id}, timeout_sec=send_timeout_sec, max_retries=0, trace_id=trace_id)
    ok = await _safe_send(
        ws,
        {
            "kind": "feature",
            "scenario": "normal",
            "session_id": session_id,
            "payload_b64": _b64(feature),
            "chunk_offset": 0,
            "chunk_total": len(feature),
        },
        timeout_sec=send_timeout_sec,
        max_retries=3,
        trace_id=trace_id,
    )
    if ok:
        log_event("info", "sent_feature", trace_id=trace_id, session_id=session_id, bytes=len(feature))


async def _scenario_stress(ws, trace_id: str, session_id: str, rng: random.Random, n: int, send_timeout_sec: float):
    await _safe_send(ws, {"kind": "meta", "trace_id": trace_id}, timeout_sec=send_timeout_sec, max_retries=0, trace_id=trace_id)
    first_feature_sent = False
    for i in range(n):
        if i % 20 == 0:
            log_event("info", "stress_progress", trace_id=trace_id, session_id=session_id, i=i)

        audio = _rand_bytes(rng, 256)
        await _safe_send(
            ws,
            {"kind": "audio", "scenario": "stress", "session_id": session_id, "payload_b64": _b64(audio), "i": i},
            timeout_sec=send_timeout_sec,
            max_retries=1,
            trace_id=trace_id,
        )

        feature = _rand_bytes(rng, 128)
        ok = await _safe_send(
            ws,
            {
                "kind": "feature",
                "scenario": "stress",
                "session_id": session_id,
                "payload_b64": _b64(feature),
                "chunk_offset": 0,
                "chunk_total": 128,
                "i": i,
            },
            timeout_sec=send_timeout_sec,
            max_retries=3 if not first_feature_sent else 1,
            trace_id=trace_id,
        )
        if ok and not first_feature_sent:
            first_feature_sent = True


async def _scenario_resume(gateway_ws: str, trace_id: str, session_id: str, feature: bytes, backend_base_url: str, send_timeout_sec: float):
    first = feature[:64]
    second = feature[64:]

    async with websockets.connect(gateway_ws) as ws:
        await _safe_send(ws, {"kind": "meta", "trace_id": trace_id}, timeout_sec=send_timeout_sec, max_retries=0, trace_id=trace_id)
        await _safe_send(
            ws,
            {
                "kind": "feature",
                "scenario": "resume",
                "session_id": session_id,
                "payload_b64": _b64(first),
                "chunk_offset": 0,
                "chunk_total": 128,
            },
            timeout_sec=send_timeout_sec,
            max_retries=3,
            trace_id=trace_id,
        )
        log_event("info", "resume_disconnect", trace_id=trace_id, session_id=session_id, sent_bytes=len(first))

    await asyncio.sleep(0.2)

    missing = await _get_missing_ranges(backend_base_url, session_id)
    log_event("info", "resume_missing_ranges", trace_id=trace_id, session_id=session_id, missing_ranges=missing)

    async with websockets.connect(gateway_ws) as ws2:
        await _safe_send(ws2, {"kind": "meta", "trace_id": trace_id}, timeout_sec=send_timeout_sec, max_retries=0, trace_id=trace_id)
        log_event("info", "resume_reconnect", trace_id=trace_id, session_id=session_id)

        if missing:
            for s, e in missing:
                s = int(s)
                e = int(e)
                chunk = feature[s:e]
                await _safe_send(
                    ws2,
                    {
                        "kind": "feature",
                        "scenario": "resume",
                        "session_id": session_id,
                        "payload_b64": _b64(chunk),
                        "chunk_offset": s,
                        "chunk_total": 128,
                    },
                    timeout_sec=send_timeout_sec,
                    max_retries=3,
                    trace_id=trace_id,
                )
        else:
            await _safe_send(
                ws2,
                {
                    "kind": "feature",
                    "scenario": "resume",
                    "session_id": session_id,
                    "payload_b64": _b64(second),
                    "chunk_offset": 64,
                    "chunk_total": 128,
                },
                timeout_sec=send_timeout_sec,
                max_retries=3,
                trace_id=trace_id,
            )


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=["normal", "resume", "stress"], required=True)
    ap.add_argument("--gateway-ws", default=os.environ.get("GATEWAY_WS", "ws://ble-gateway:8787"))
    ap.add_argument("--backend-base-url", default=os.environ.get("BACKEND_BASE_URL", "http://backend:8000"))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--session-id", default="")
    ap.add_argument("--trace-id", default="")
    ap.add_argument("--send-timeout-sec", type=float, default=0.5)
    ap.add_argument("--result-timeout-sec", type=float, default=30.0)
    ap.add_argument("--stress-n", type=int, default=200)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    trace_id = args.trace_id or f"trace-{args.seed}-{uuid.uuid4().hex[:8]}"
    session_id = args.session_id or f"session-{uuid.uuid4().hex[:8]}"

    log_event("info", "start", scenario=args.scenario, trace_id=trace_id, session_id=session_id, gateway_ws=args.gateway_ws)

    if args.scenario == "resume":
        feature = _rand_bytes(rng, 128)
        await _scenario_resume(
            gateway_ws=args.gateway_ws,
            trace_id=trace_id,
            session_id=session_id,
            feature=feature,
            backend_base_url=args.backend_base_url,
            send_timeout_sec=args.send_timeout_sec,
        )
        await _poll_result(args.backend_base_url, trace_id, timeout_sec=args.result_timeout_sec)
        log_event("info", "done", trace_id=trace_id, session_id=session_id)
        return

    async with websockets.connect(args.gateway_ws) as ws:
        if args.scenario == "normal":
            feature = _rand_bytes(rng, 128)
            await _scenario_normal(ws, trace_id=trace_id, session_id=session_id, feature=feature, send_timeout_sec=args.send_timeout_sec)
        else:
            await _scenario_stress(ws, trace_id=trace_id, session_id=session_id, rng=rng, n=args.stress_n, send_timeout_sec=args.send_timeout_sec)

    await _poll_result(args.backend_base_url, trace_id, timeout_sec=args.result_timeout_sec)
    log_event("info", "done", trace_id=trace_id, session_id=session_id)


if __name__ == "__main__":
    asyncio.run(main())
