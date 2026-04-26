import argparse
import asyncio
import base64
import json
import time
import zlib

import websockets


IDLE_TIMEOUT_SEC = 600
CLEANUP_INTERVAL_SEC = 60


def _crc32_u32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


class SessionState:
    def __init__(self, session_id: str, frame_type: int, total_bytes: int):
        self.session_id = session_id
        self.frame_type = frame_type
        self.total_bytes = total_bytes
        self.buf = bytearray(total_bytes)
        self.received = bytearray(total_bytes)
        self.last_activity_ts = time.time()

    def note_activity(self) -> None:
        self.last_activity_ts = time.time()

    def write_chunk(self, offset: int, data: bytes) -> int:
        end = offset + len(data)
        if offset < 0 or end > self.total_bytes:
            raise ValueError("offset_out_of_range")
        self.buf[offset:end] = data
        self.received[offset:end] = b"\x01" * len(data)
        self.note_activity()
        return end

    def is_complete(self) -> bool:
        return all(b != 0 for b in self.received)

    def missing_ranges(self):
        ranges = []
        i = 0
        while i < self.total_bytes:
            if self.received[i] != 0:
                i += 1
                continue
            start = i
            while i < self.total_bytes and self.received[i] == 0:
                i += 1
            ranges.append([start, i])
        return ranges


async def _send(ws, obj):
    await ws.send(json.dumps(obj))


async def _handle_message(ws, sessions, msg):
    op = msg.get("op")

    if op == "session_init":
        session_id = msg.get("session_id")
        frame_type = int(msg.get("frame_type"))
        total_bytes = int(msg.get("total_bytes"))
        if not session_id or total_bytes <= 0:
            await _send(ws, {"op": "session_ack", "session_id": session_id, "accepted": False})
            return
        sessions[session_id] = SessionState(session_id, frame_type, total_bytes)
        await _send(ws, {"op": "session_ack", "session_id": session_id, "accepted": True})
        return

    if op == "chunk":
        session_id = msg.get("session_id")
        s = sessions.get(session_id)
        if s is None:
            await _send(ws, {"op": "error", "session_id": session_id, "code": 1000})
            return
        try:
            offset = int(msg.get("offset"))
            data_b64 = msg.get("data", "")
            raw = base64.b64decode(data_b64, validate=True)
        except Exception:
            await _send(ws, {"op": "error", "session_id": session_id, "code": 1002})
            return
        want_crc = int(msg.get("crc32"))
        if _crc32_u32(raw) != want_crc:
            await _send(ws, {"op": "error", "session_id": session_id, "code": 1003})
            return
        try:
            next_offset = s.write_chunk(offset, raw)
        except Exception:
            await _send(ws, {"op": "error", "session_id": session_id, "code": 1001})
            return
        await _send(ws, {"op": "chunk_ack", "session_id": session_id, "offset": offset, "next_offset": next_offset})
        return

    if op == "session_resume":
        session_id = msg.get("session_id")
        s = sessions.get(session_id)
        if s is None:
            await _send(ws, {"op": "error", "session_id": session_id, "code": 1000})
            return
        s.note_activity()
        await _send(
            ws,
            {"op": "session_state", "session_id": session_id, "received_bytes": s.total_bytes - sum(1 for b in s.received if b == 0), "missing_ranges": s.missing_ranges()},
        )
        return

    if op == "session_complete":
        session_id = msg.get("session_id")
        s = sessions.get(session_id)
        if s is None:
            await _send(ws, {"op": "error", "session_id": session_id, "code": 1000})
            return
        s.note_activity()
        if not s.is_complete():
            await _send(ws, {"op": "session_state", "session_id": session_id, "received_bytes": s.total_bytes - sum(1 for b in s.received if b == 0), "missing_ranges": s.missing_ranges()})
            return
        await _send(ws, {"op": "result", "session_id": session_id, "result_type": "mock", "payload": {"similarity": 0.92}})
        return

    await _send(ws, {"op": "error", "code": 1004})


async def _cleanup_loop(sessions):
    while True:
        now = time.time()
        dead = []
        for sid, s in sessions.items():
            if now - s.last_activity_ts > IDLE_TIMEOUT_SEC:
                dead.append(sid)
        for sid in dead:
            sessions.pop(sid, None)
        await asyncio.sleep(CLEANUP_INTERVAL_SEC)


async def serve(host: str, port: int, demo: bool):
    sessions = {}
    asyncio.create_task(_cleanup_loop(sessions))

    async def handler(ws):
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except Exception:
                await _send(ws, {"op": "error", "code": 1005})
                continue
            await _handle_message(ws, sessions, msg)

    async with websockets.serve(handler, host, port):
        if demo:
            print(f"Server ready on ws://{host}:{port}", flush=True)
        await asyncio.Future()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    asyncio.run(serve(args.host, args.port, args.demo))


if __name__ == "__main__":
    main()

