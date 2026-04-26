#!/usr/bin/env python3
import argparse
import random
import statistics
import sys


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * p
    f = int(k)
    c = min(f + 1, len(values_sorted) - 1)
    if f == c:
        return float(values_sorted[f])
    d0 = values_sorted[f] * (c - k)
    d1 = values_sorted[c] * (k - f)
    return float(d0 + d1)


def simulate(frames: int, frame_ms: int, loss_rate: float, bitrate: int, payload_max: int, seed: int) -> dict:
    rng = random.Random(seed)

    payload_bytes = int(round((bitrate / 8.0) * (frame_ms / 1000.0)))
    payload_bytes = min(payload_bytes, payload_max)

    generated = []
    seq = 0
    ts_ms = 0
    for _ in range(frames):
        generated.append((seq, ts_ms, payload_bytes))
        seq = (seq + 1) & 0xFFFF
        ts_ms += frame_ms

    received = []
    for pkt in generated:
        if rng.random() < loss_rate:
            continue
        received.append(pkt)

    observed_loss = 1.0 - (len(received) / float(len(generated))) if generated else 0.0

    audio_bps = (payload_bytes + 6) * 8 * (1000.0 / frame_ms) if frame_ms > 0 else 0.0

    encode_ms_mean = 5.0
    ble_ms_mean = 20.0
    jitter_buffer_ms_max = 50.0

    delays = []
    for _ in received:
        encode_ms = max(0.0, rng.gauss(encode_ms_mean, 1.0))
        ble_ms = max(0.0, rng.gauss(ble_ms_mean, 5.0))
        reorder_ms = rng.uniform(0.0, jitter_buffer_ms_max)
        delays.append(encode_ms + ble_ms + reorder_ms)

    result = {
        "payload_bytes": payload_bytes,
        "frames": frames,
        "received": len(received),
        "observed_loss": observed_loss,
        "audio_bps": audio_bps,
        "delay_p50": percentile(delays, 0.50),
        "delay_p95": percentile(delays, 0.95),
        "delay_p99": percentile(delays, 0.99),
        "delay_mean": statistics.mean(delays) if delays else 0.0,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loss-rate", type=float, default=0.01)
    parser.add_argument("--frames", type=int, default=1000)
    parser.add_argument("--frame-ms", type=int, default=20)
    parser.add_argument("--bitrate", type=int, default=64000)
    parser.add_argument("--payload-max", type=int, default=160)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if args.frames <= 0:
        print("frames must be > 0", file=sys.stderr)
        return 2
    if not (0.0 <= args.loss_rate < 1.0):
        print("loss-rate must be in [0, 1)", file=sys.stderr)
        return 2

    r = simulate(
        frames=args.frames,
        frame_ms=args.frame_ms,
        loss_rate=args.loss_rate,
        bitrate=args.bitrate,
        payload_max=args.payload_max,
        seed=args.seed,
    )

    print("# BLE Audio Throughput Simulator Report")
    print("")
    print("## Config")
    print(f"- frames: {args.frames}")
    print(f"- frame_ms: {args.frame_ms}")
    print(f"- bitrate: {args.bitrate}")
    print(f"- payload_max: {args.payload_max}")
    print(f"- loss_rate: {args.loss_rate}")
    print(f"- seed: {args.seed}")
    print("")
    print("## Result")
    print("| Metric | Value |")
    print("|---|---:|")
    print(f"| payload_bytes | {r['payload_bytes']} |")
    print(f"| received_frames | {r['received']} |")
    print(f"| observed_loss | {r['observed_loss'] * 100:.2f}% |")
    print(f"| estimated_audio_bps (payload+6B header) | {r['audio_bps']:.0f} |")
    print(f"| delay_mean_ms | {r['delay_mean']:.2f} |")
    print(f"| delay_p50_ms | {r['delay_p50']:.2f} |")
    print(f"| delay_p95_ms | {r['delay_p95']:.2f} |")
    print(f"| delay_p99_ms | {r['delay_p99']:.2f} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

