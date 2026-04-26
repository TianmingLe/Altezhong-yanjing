import asyncio
import base64
import os
import struct
import uuid
import zlib

import websockets


def crc32_u32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def build_frame(seq: int, timestamp_ms: int, feature_i8: bytes) -> bytes:
    header = struct.pack("<BBHII", 0x02, 33, seq & 0xFFFF, timestamp_ms & 0xFFFFFFFF, len(feature_i8))
    return header + feature_i8


async def main():
    ws_url = os.environ.get("RELAY_WS_URL", "ws://127.0.0.1:8766")
    session_id = str(uuid.uuid4())
    feature = os.urandom(128)
    frame = build_frame(seq=1, timestamp_ms=1, feature_i8=feature)

    async with websockets.connect(ws_url) as ws:
        await ws.send(
            '{"op":"session_init","session_id":"%s","frame_type":2,"total_bytes":%d}' % (session_id, len(frame))
        )
        resp = await ws.recv()
        if '"accepted": true' not in resp and '"accepted":true' not in resp:
            raise RuntimeError(resp)

        b64 = base64.b64encode(frame).decode("ascii")
        await ws.send(
            '{"op":"chunk","session_id":"%s","offset":0,"data":"%s","crc32":%d}' % (session_id, b64, crc32_u32(frame))
        )
        ack = await ws.recv()
        if '"op": "chunk_ack"' not in ack and '"op":"chunk_ack"' not in ack:
            raise RuntimeError(ack)

        await ws.send('{"op":"session_complete","session_id":"%s","sha256":"%s"}' % (session_id, "0" * 64))
        out = await ws.recv()
        print(f"✅ Session complete, result: {out}")


if __name__ == "__main__":
    asyncio.run(main())

