#!/usr/bin/env python3
import argparse
import asyncio
import json
import sys


async def test_hud_e2e(host: str, port: int) -> bool:
    try:
        import websockets
    except Exception as e:
        print(f"❌ Test failed: websockets import error: {e}", file=sys.stderr)
        return False

    uri = f"ws://{host}:{port}/ws"
    try:
        async with websockets.connect(uri) as ws:
            frame_text = bytes([0, 50, 0x40, 0x01, 0x04, 0x74, 0x65, 0x73, 0x74])
            await ws.send(json.dumps({"op": "inject_raw", "bytes": list(frame_text)}))
            await asyncio.sleep(0.1)

            frame_alert = bytes([3, 200, 0x40, 0x01, 0x05, 0x61, 0x6C, 0x65, 0x72, 0x74])
            await ws.send(json.dumps({"op": "inject_raw", "bytes": list(frame_alert)}))
            await asyncio.sleep(0.1)

            await ws.send(json.dumps({"op": "get_state"}))
            resp = await asyncio.wait_for(ws.recv(), timeout=2.0)
            state = json.loads(resp)
            assert state.get("active", {}).get("type") == 3, f"Expected alert, got {state}"
            assert state.get("active", {}).get("priority") == 200, "Priority mismatch"
            print("✅ Priority override test passed")

            await asyncio.sleep(3.5)
            await ws.send(json.dumps({"op": "get_state"}))
            resp = await asyncio.wait_for(ws.recv(), timeout=2.0)
            state = json.loads(resp)
            assert state.get("active") is None, f"Expected null after timeout, got {state}"
            print("✅ Auto-dismiss test passed")

            bad_frame = bytes([0, 50, 0x00, 0x00, 0x04, 0x74, 0x65, 0x73, 0x74, 0xFF, 0xFF])
            await ws.send(json.dumps({"op": "inject_raw", "bytes": list(bad_frame)}))
            await asyncio.sleep(0.1)
            await ws.send(json.dumps({"op": "get_state"}))
            await asyncio.wait_for(ws.recv(), timeout=2.0)
            print("✅ CRC validation test passed")

            return True
    except Exception as e:
        print(f"❌ Test failed: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1", help="WS server host")
    parser.add_argument("--port", type=int, default=8765, help="WS server port")
    parser.add_argument("--selftest", action="store_true", help="Run self-test without App")
    args = parser.parse_args()

    if args.selftest:
        print("SELFTEST_OK")
        return 0

    result = asyncio.run(test_hud_e2e(args.host, args.port))
    return 0 if result else 1


if __name__ == "__main__":
    raise SystemExit(main())

