import asyncio
import json
import os
import signal
import time
from collections import deque

import httpx
import websockets


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log_event(level: str, event: str, **fields):
    payload = {"ts": _ts(), "level": level, "service": "ble-gateway", "event": event}
    payload.update(fields)
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _estimate_bytes(item: dict) -> int:
    b64 = item.get("payload_b64")
    if isinstance(b64, str) and b64:
        n = len(b64)
        pad = 0
        if b64.endswith("=="):
            pad = 2
        elif b64.endswith("="):
            pad = 1
        return max(0, (n * 3) // 4 - pad)
    return len(json.dumps(item, ensure_ascii=False).encode("utf-8"))


class BoundedQueue:
    def __init__(self, max_items: int, max_bytes: int):
        self._max_items = max_items
        self._max_bytes = max_bytes
        self._items = deque()
        self._bytes = 0
        self._pending = 0
        self._cv = asyncio.Condition()

    def qsize(self) -> int:
        return len(self._items)

    def qbytes(self) -> int:
        return self._bytes

    async def put(self, item: dict) -> None:
        size = _estimate_bytes(item)
        async with self._cv:
            if size > self._max_bytes:
                return
            while len(self._items) >= self._max_items or self._bytes + size > self._max_bytes:
                await self._cv.wait()
            self._items.append((item, size))
            self._bytes += size
            self._pending += 1
            self._cv.notify_all()

    async def get(self, timeout: float) -> dict | None:
        async with self._cv:
            if not self._items:
                try:
                    await asyncio.wait_for(self._cv.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    return None
            if not self._items:
                return None
            item, size = self._items.popleft()
            self._bytes -= size
            self._cv.notify_all()
            return item

    async def task_done(self) -> None:
        async with self._cv:
            self._pending -= 1
            self._cv.notify_all()

    async def join(self) -> None:
        async with self._cv:
            while self._pending > 0:
                await self._cv.wait()


def _endpoint_for(kind: str) -> str:
    if kind == "feature":
        return "/demo/ingest/feature"
    return "/demo/ingest/audio"


async def forward_loop(queue: BoundedQueue, backend_base_url: str, stop: asyncio.Event) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            if stop.is_set() and queue.qsize() == 0:
                return
            item = await queue.get(timeout=0.5)
            if item is None:
                continue
            kind = str(item.get("kind") or "audio")
            try:
                url = f"{backend_base_url}{_endpoint_for(kind)}"
                r = await client.post(url, json=item)
                r.raise_for_status()
                log_event("info", "forward_ok", kind=kind, trace_id=item.get("trace_id"), session_id=item.get("session_id"))
            except Exception as e:
                log_event("error", "forward_fail", kind=kind, error=str(e), trace_id=item.get("trace_id"), session_id=item.get("session_id"))
            finally:
                await queue.task_done()


async def serve_ws(host: str, port: int, queue: BoundedQueue, stop: asyncio.Event) -> None:
    async def handler(ws):
        trace_id = None
        peer = str(getattr(ws, "remote_address", ""))
        log_event("info", "ws_connected", peer=peer)
        try:
            async for raw in ws:
                if stop.is_set():
                    break
                try:
                    msg = json.loads(raw)
                except Exception:
                    log_event("warn", "bad_json", peer=peer)
                    continue

                if msg.get("kind") == "meta":
                    trace_id = msg.get("trace_id")
                    log_event("info", "trace_id_set", trace_id=trace_id, peer=peer)
                    continue

                if trace_id:
                    msg["trace_id"] = trace_id

                await queue.put(msg)
        finally:
            log_event("info", "ws_disconnected", peer=peer)

    async with websockets.serve(handler, host, port):
        log_event("info", "ready", ws_url=f"ws://{host}:{port}")
        await stop.wait()


async def main() -> None:
    host = os.environ.get("GATEWAY_HOST", "0.0.0.0")
    port = int(os.environ.get("GATEWAY_PORT", "8787"))
    backend_base_url = os.environ.get("BACKEND_BASE_URL", "http://backend:8000")
    max_items = int(os.environ.get("GATEWAY_QUEUE_MAX_ITEMS", "500"))
    max_bytes = int(os.environ.get("GATEWAY_QUEUE_MAX_BYTES", str(2 * 1024 * 1024)))
    drain_timeout = float(os.environ.get("GATEWAY_DRAIN_TIMEOUT_SEC", "5"))

    stop = asyncio.Event()
    reason = {"value": "unknown"}

    def _sig_handler(sig, *_):
        if stop.is_set():
            return
        stop.set()
        if sig == signal.SIGTERM:
            reason["value"] = "sigterm"
        elif sig == signal.SIGINT:
            reason["value"] = "sigint"
        else:
            reason["value"] = "signal"

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    queue = BoundedQueue(max_items=max_items, max_bytes=max_bytes)

    forward_task = asyncio.create_task(forward_loop(queue, backend_base_url, stop))
    ws_task = asyncio.create_task(serve_ws(host, port, queue, stop))

    await stop.wait()
    log_event("info", "draining_start", pending_items=queue.qsize(), pending_bytes=queue.qbytes())

    try:
        await asyncio.wait_for(queue.join(), timeout=drain_timeout)
    except asyncio.TimeoutError:
        log_event("warn", "draining_timeout", pending_items=queue.qsize(), pending_bytes=queue.qbytes())

    forward_task.cancel()
    ws_task.cancel()
    await asyncio.gather(forward_task, ws_task, return_exceptions=True)

    log_event("info", "gateway_shutdown", reason=reason["value"], pending_items=queue.qsize(), pending_bytes=queue.qbytes())


if __name__ == "__main__":
    asyncio.run(main())
