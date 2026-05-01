import asyncio
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "omi" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


def test_memory_sink_is_bounded():
    from utils.demo.event_sink import MemorySink

    sink = MemorySink(maxlen=3)

    async def run():
        await sink.emit({"op": "a"})
        await sink.emit({"op": "b"})
        await sink.emit({"op": "c"})
        await sink.emit({"op": "d"})

    asyncio.run(run())

    events = sink.snapshot()
    assert [e["op"] for e in events] == ["b", "c", "d"]


def test_redis_sink_uses_xadd():
    from utils.demo.event_sink import RedisSink

    calls = []

    class FakeRedis:
        async def xadd(self, stream, fields, maxlen=None, approximate=None):
            calls.append((stream, fields, maxlen, approximate))
            return "1-0"

    sink = RedisSink(redis=FakeRedis(), stream="demo:events:t1", maxlen=1000)

    async def run():
        await sink.emit({"op": "session_init", "session_id": "s1"})

    asyncio.run(run())

    assert calls
    stream, fields, maxlen, approximate = calls[0]
    assert stream == "demo:events:t1"
    assert "payload" in fields
    assert maxlen == 1000


def test_composite_sink_degrades_on_redis_error():
    from utils.demo.event_sink import CompositeSink, MemorySink, RedisSink

    class BadRedis:
        async def xadd(self, *_args, **_kwargs):
            raise RuntimeError("redis_down")

    memory = MemorySink(maxlen=1000)
    sink = CompositeSink([RedisSink(redis=BadRedis(), stream="demo:events:t2", maxlen=1000), memory])

    async def run():
        await sink.emit({"op": "chunk", "session_id": "s2"})
        await sink.emit({"op": "result", "session_id": "s2"})

    asyncio.run(run())

    events = memory.snapshot()
    assert [e["op"] for e in events] == ["chunk", "result"]


def test_real_redis_integration_optional():
    import os
    import pytest

    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL not set")

    from utils.demo.event_sink import RedisSink

    async def run():
        import redis.asyncio as redis

        r = redis.from_url(redis_url, decode_responses=True)
        sink = RedisSink(redis=r, stream="demo:events:it", maxlen=1000)
        await sink.emit({"op": "it", "session_id": "s-it"})
        resp = await r.xread({"demo:events:it": "0-0"}, count=1, block=1000)
        assert resp
        await r.close()
        await r.connection_pool.disconnect()

    asyncio.run(run())

