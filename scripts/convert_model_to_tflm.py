#!/usr/bin/env python3
import argparse
import pathlib
import sys


def emit_c_array(data: bytes, symbol: str) -> str:
    lines = []
    lines.append(f"const unsigned char {symbol}[] = {{")
    for i, b in enumerate(data):
        if i % 12 == 0:
            lines.append("    ")
        lines[-1] += f"0x{b:02x}, "
        if i % 12 == 11:
            lines.append("")
    if len(data) % 12 != 0:
        lines.append("")
    lines.append("};")
    lines.append(f"const unsigned int {symbol}_len = {len(data)};")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tflite", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--symbol", default="g_feature_model")
    args = ap.parse_args()

    tflite_path = pathlib.Path(args.tflite)
    out_path = pathlib.Path(args.out)

    if not tflite_path.exists():
        print(f"missing --tflite: {tflite_path}", file=sys.stderr)
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = tflite_path.read_bytes()
    out_path.write_text(emit_c_array(data, args.symbol), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

