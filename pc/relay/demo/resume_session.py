import asyncio
import base64
import os
import struct
import uuid
import zlib

import websockets


def crc32_u32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def build_frame(seq: int, timestamp_ms: int, payload: bytes) -> bytes:
    header = struct.pack("<BBHII", 0x02, 33, seq & 0xFFFF, timestamp_ms & 0xFFFFFFFF, len(payload))
    return header + payload


async def send_chunk(ws, session_id: str, offset: int, chunk: bytes):
    b64 = base64.b64encode(chunk).decode("ascii")
    await ws.send(
        '{"op":"chunk","session_id":"%s","offset":%d,"data":"%s","crc32":%d}' % (session_id, offset, b64, crc32_u32(chunk))
    )
    return await ws.recv()


async def main():
    ws_url = os.environ.get("RELAY_WS_URL", "ws://127.0.0.1:8766")
    session_id = str(uuid.uuid4())
    payload = os.urandom(1188)
    frame = build_frame(seq=2, timestamp_ms=2, payload=payload)

    chunk_size = 512
    c0 = frame[0:chunk_size]
    c1 = frame[chunk_size : chunk_size * 2]
    c2 = frame[chunk_size * 2 :]

    async with websockets.connect(ws_url) as ws:
        await ws.send(
            '{"op":"session_init","session_id":"%s","frame_type":2,"total_bytes":%d}' % (session_id, len(frame))
        )
        resp = await ws.recv()
        if '"accepted": true' not in resp and '"accepted":true' not in resp:
            raise RuntimeError(resp)
        await send_chunk(ws, session_id, 0, c0)
        await send_chunk(ws, session_id, chunk_size, c1)

    async with websockets.connect(ws_url) as ws2:
        await ws2.send('{"op":"session_resume","session_id":"%s","last_ack_offset":%d}' % (session_id, chunk_size * 2))
        state = await ws2.recv()
        if '"op": "session_state"' not in state and '"op":"session_state"' not in state:
            raise RuntimeError(state)

        await send_chunk(ws2, session_id, chunk_size * 2, c2)
        await ws2.send('{"op":"session_complete","session_id":"%s","sha256":"%s"}' % (session_id, "0" * 64))
        out = await ws2.recv()
        print("✅ Resume complete")
        print(out)


if __name__ == "__main__":
    asyncio.run(main())

