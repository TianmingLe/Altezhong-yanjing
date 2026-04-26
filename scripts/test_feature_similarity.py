#!/usr/bin/env python3
import argparse
import math
import random
import statistics
import sys


def dequant_int8(vec, scale, zero_point):
    return [(float(v) - float(zero_point)) * float(scale) for v in vec]


def l2_norm(vec):
    s = 0.0
    for x in vec:
        s += x * x
    return math.sqrt(s)


def cosine(a, b):
    na = l2_norm(a)
    nb = l2_norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    dot = 0.0
    for x, y in zip(a, b):
        dot += x * y
    return dot / (na * nb)


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    idx = int(round((p / 100.0) * (len(sorted_vals) - 1)))
    if idx < 0:
        idx = 0
    if idx >= len(sorted_vals):
        idx = len(sorted_vals) - 1
    return sorted_vals[idx]


def clamp_int8(x):
    if x < -128:
        return -128
    if x > 127:
        return 127
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--scale", type=float, default=0.1)
    ap.add_argument("--zero-point", type=int, default=0)
    ap.add_argument("--noise", type=int, default=2)
    args = ap.parse_args()

    try:
        import tflite_runtime.interpreter  # noqa: F401
        runtime = "tflite-runtime"
    except Exception:
        try:
            import tensorflow as tf  # noqa: F401
            runtime = "tensorflow"
        except Exception:
            runtime = None

    if runtime is None:
        print("Mock-only mode (tflite-runtime not available)")
    else:
        print(f"Runtime available: {runtime} (still running mock mode)")

    rng = random.Random(args.seed)
    sims = []

    for _ in range(args.frames):
        ref_i8 = [rng.randint(-128, 127) for _ in range(128)]
        dev_i8 = [clamp_int8(v + rng.randint(-args.noise, args.noise)) for v in ref_i8]

        ref_f = dequant_int8(ref_i8, args.scale, args.zero_point)
        dev_f = dequant_int8(dev_i8, args.scale, args.zero_point)
        sims.append(cosine(ref_f, dev_f))

    sims_sorted = sorted(sims)
    p50 = percentile(sims_sorted, 50)
    p95 = percentile(sims_sorted, 95)
    mn = sims_sorted[0] if sims_sorted else 0.0
    mean = statistics.fmean(sims) if sims else 0.0

    print(f"frames={args.frames} scale={args.scale} zero_point={args.zero_point} noise={args.noise}")
    print(f"cosine: p50={p50:.6f} p95={p95:.6f} min={mn:.6f} mean={mean:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

