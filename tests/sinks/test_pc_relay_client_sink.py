import asyncio
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "omi" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


def test_pc_relay_client_emit_does_not_block_on_sink_error():
    from utils.demo.pc_relay_client import PcRelayClient

    class BadSink:
        async def emit(self, _event):
            raise RuntimeError("down")

    c = PcRelayClient(relay_url="ws://127.0.0.1:1", sink=BadSink())

    async def run():
        await c._emit_event("session_init", session_id="s1", seq=0, retry_count=0, elapsed_ms=1)

    asyncio.run(run())


def test_pc_relay_client_emits_required_fields():
    from utils.demo.event_sink import MemorySink
    from utils.demo.pc_relay_client import PcRelayClient

    sink = MemorySink(maxlen=10)
    c = PcRelayClient(relay_url="ws://127.0.0.1:1", sink=sink)

    async def run():
        await c._emit_event("chunk", session_id="s2", seq=3, retry_count=2, elapsed_ms=9, offset=64)

    asyncio.run(run())

    ev = sink.snapshot()[-1]
    assert ev["op"] == "chunk"
    assert ev["session_id"] == "s2"
    assert ev["seq"] == 3
    assert ev["retry_count"] == 2
    assert ev["elapsed_ms"] == 9
    assert "ts" in ev

