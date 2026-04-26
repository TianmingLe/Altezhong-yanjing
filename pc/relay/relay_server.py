import argparse
import asyncio
import base64
import json
import time
import zlib

import websockets

from protocols.relay_error_codes import RelayErrorCode


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
        self.received_ranges = []
        self.last_activity_ts = time.time()

    def note_activity(self) -> None:
        self.last_activity_ts = time.time()

    def write_chunk(self, offset: int, data: bytes) -> int:
        end = offset + len(data)
        if offset < 0 or end > self.total_bytes:
            raise ValueError("offset_out_of_range")
        self.buf[offset:end] = data
        self._add_received_range(offset, end)
        self.note_activity()
        return end

    def _add_received_range(self, start: int, end: int) -> None:
        if start >= end:
            return
        ranges = self.received_ranges
        ranges.append([start, end])
        ranges.sort(key=lambda r: r[0])
        merged = []
        for s, e in ranges:
            if not merged:
                merged.append([s, e])
                continue
            ps, pe = merged[-1]
            if s <= pe:
                if e > pe:
                    merged[-1][1] = e
            else:
                merged.append([s, e])
        self.received_ranges = merged

    def received_bytes(self) -> int:
        n = 0
        for s, e in self.received_ranges:
            n += e - s
        return n

    def max_received_end(self) -> int:
        if not self.received_ranges:
            return 0
        return self.received_ranges[-1][1]

    def is_complete(self) -> bool:
        return len(self.received_ranges) == 1 and self.received_ranges[0][0] == 0 and self.received_ranges[0][1] == self.total_bytes

    def missing_ranges(self):
        if not self.received_ranges:
            return [[0, self.total_bytes]]
        missing = []
        cur = 0
        for s, e in self.received_ranges:
            if s > cur:
                missing.append([cur, s])
            if e > cur:
                cur = e
        if cur < self.total_bytes:
            missing.append([cur, self.total_bytes])
        return missing


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
            await _send(ws, {"op": "error", "session_id": session_id, "code": RelayErrorCode.RELAY_ERR_SESSION_NOT_FOUND})
            return
        try:
            offset = int(msg.get("offset"))
            data_b64 = msg.get("data", "")
            raw = base64.b64decode(data_b64, validate=True)
        except Exception:
            await _send(ws, {"op": "error", "session_id": session_id, "code": RelayErrorCode.RELAY_ERR_BAD_BASE64})
            return
        want_crc = int(msg.get("crc32"))
        if _crc32_u32(raw) != want_crc:
            await _send(ws, {"op": "error", "session_id": session_id, "code": RelayErrorCode.RELAY_ERR_CRC_MISMATCH})
            return
        try:
            next_offset = s.write_chunk(offset, raw)
        except Exception:
            await _send(ws, {"op": "error", "session_id": session_id, "code": RelayErrorCode.RELAY_ERR_OFFSET_OUT_OF_RANGE})
            return
        await _send(ws, {"op": "chunk_ack", "session_id": session_id, "offset": offset, "next_offset": next_offset})
        return

    if op == "session_resume":
        session_id = msg.get("session_id")
        s = sessions.get(session_id)
        if s is None:
            await _send(ws, {"op": "error", "session_id": session_id, "code": RelayErrorCode.RELAY_ERR_SESSION_NOT_FOUND})
            return
        try:
            last_ack_offset = int(msg.get("last_ack_offset"))
        except Exception:
            await _send(ws, {"op": "error", "session_id": session_id, "code": RelayErrorCode.RELAY_ERR_INVALID_OFFSET})
            return
        if last_ack_offset < 0 or last_ack_offset > s.total_bytes or last_ack_offset > s.max_received_end():
            await _send(ws, {"op": "error", "session_id": session_id, "code": RelayErrorCode.RELAY_ERR_INVALID_OFFSET})
            return
        s.note_activity()
        await _send(
            ws,
            {"op": "session_state", "session_id": session_id, "received_bytes": s.received_bytes(), "missing_ranges": s.missing_ranges()},
        )
        return

    if op == "session_complete":
        session_id = msg.get("session_id")
        s = sessions.get(session_id)
        if s is None:
            await _send(ws, {"op": "error", "session_id": session_id, "code": RelayErrorCode.RELAY_ERR_SESSION_NOT_FOUND})
            return
        s.note_activity()
        if not s.is_complete():
            await _send(ws, {"op": "session_state", "session_id": session_id, "received_bytes": s.received_bytes(), "missing_ranges": s.missing_ranges()})
            return
        await _send(ws, {"op": "result", "session_id": session_id, "result_type": "mock", "payload": {"similarity": 0.92}})
        return

    await _send(ws, {"op": "error", "code": RelayErrorCode.RELAY_ERR_BAD_OP})


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
                await _send(ws, {"op": "error", "code": RelayErrorCode.RELAY_ERR_BAD_JSON})
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
