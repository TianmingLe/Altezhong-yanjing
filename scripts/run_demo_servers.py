#!/usr/bin/env python3
import argparse
import os
import signal
import socket
import subprocess
import sys
import time


def _is_port_open(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.2)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def _start_backend() -> subprocess.Popen:
    backend_dir = os.path.join(os.getcwd(), "omi", "backend")
    cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"]
    return subprocess.Popen(cmd, cwd=backend_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _start_backend_fallback() -> subprocess.Popen:
    backend_dir = os.path.join(os.getcwd(), "omi", "backend")
    cmd = [sys.executable, "-m", "http.server", "8000"]
    return subprocess.Popen(cmd, cwd=backend_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _start_relay() -> subprocess.Popen:
    relay_dir = os.path.join(os.getcwd(), "pc", "relay")
    cmd = [sys.executable, "relay_server.py", "--demo", "--host", "127.0.0.1", "--port", "8766"]
    return subprocess.Popen(cmd, cwd=relay_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exit-after-sec", type=float, default=0.0)
    args = ap.parse_args()

    procs = []

    def shutdown():
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                pass

    def handle_sigint(_signum, _frame):
        shutdown()
        raise SystemExit(130)

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    print("Starting backend: http://127.0.0.1:8000", flush=True)
    backend = _start_backend()
    procs.append(backend)

    print("Starting relay: ws://127.0.0.1:8766", flush=True)
    relay = _start_relay()
    procs.append(relay)

    t0 = time.time()
    relay_ready = False
    while time.time() - t0 < 5 and relay.poll() is None:
        assert relay.stdout is not None
        line = relay.stdout.readline()
        if not line:
            continue
        line = line.strip()
        if "Server ready on ws://" in line:
            print(line, flush=True)
            relay_ready = True
            break

    if backend.poll() is not None:
        print("Backend failed to start (missing deps). Falling back to http.server on :8000", flush=True)
        backend_fb = _start_backend_fallback()
        procs[0] = backend_fb
        backend = backend_fb

    backend_ok = False
    t1 = time.time()
    while time.time() - t1 < 10:
        if _is_port_open("127.0.0.1", 8000):
            backend_ok = True
            break
        if backend.poll() is not None:
            break
        time.sleep(0.2)

    if not backend_ok:
        if backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(timeout=3)
            except Exception:
                pass
        print("Backend not ready. Falling back to http.server on :8000", flush=True)
        backend_fb = _start_backend_fallback()
        procs[0] = backend_fb
        backend = backend_fb
        t2 = time.time()
        while time.time() - t2 < 3:
            if _is_port_open("127.0.0.1", 8000):
                backend_ok = True
                break
            time.sleep(0.2)

    if backend_ok and relay_ready:
        print("Ready: backend=8000 relay=8766", flush=True)

    if args.exit_after_sec and args.exit_after_sec > 0:
        time.sleep(args.exit_after_sec)
        shutdown()
        return 0

    print("Press Ctrl+C to stop", flush=True)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
