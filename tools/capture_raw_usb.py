#!/usr/bin/env python3
"""Capture exact read-only EH-800 USB TX/RX bytes as hex and binary-safe JSON.

Diagnostic framing uses a quiet-time heuristic; this is not a guarantee
that every fragmented network response has arrived. Never run alongside HA.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

# Deliberately limited to read-oriented commands. FIRMWARE and arbitrary
# commands are not exposed in this production-branch capture tool.
COMMANDS = ("MEASUREMENTS", "LIST", "DEVINFO", "OSINFO", "TIME", "TYPE objects.dat")


def collect(port, command, deadline=9.0, quiet_time=0.8):
    import serial

    payload = (command + "\n").encode("ascii")
    with serial.Serial(port, timeout=0.15, write_timeout=2, exclusive=True) as device:
        time.sleep(0.06)
        device.reset_input_buffer()
        device.write(payload)
        device.flush()
        chunks = []
        began = time.monotonic()
        last_data = None
        while time.monotonic() - began < deadline:
            chunk = device.read(4096)
            if chunk:
                chunks.append(bytes(chunk))
                last_data = time.monotonic()
            elif last_data is not None and time.monotonic() - last_data >= quiet_time:
                break
    return payload, b"".join(chunks), [c.hex(" ") for c in chunks]


def format_record(command, tx, rx, chunks):
    return {
        "schema_version": 1,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "tx_hex": tx.hex(" "),
        "rx_hex": rx.hex(" "),
        "rx_sha256": hashlib.sha256(rx).hexdigest(),
        "rx_length": len(rx),
        "rx_chunks_hex": chunks,
        "rx_preview_latin1": rx[:512].decode("latin1", errors="replace"),
        "warning": "Read capture may include private controller data; review before publishing",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--command", choices=COMMANDS, default="MEASUREMENTS")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists: refusing to overwrite a capture")
    tx, rx, chunks = collect(args.port, args.command)
    args.output.write_text(
        json.dumps(format_record(args.command, tx, rx, chunks), indent=2)
        + "\n", encoding="utf-8"
    )
    args.output.with_suffix(args.output.suffix + ".bin").write_bytes(rx)
    print(f"Wrote {len(rx)} raw RX bytes plus metadata to {args.output}")
    print("Review device-specific data before uploading these files publicly.")


if __name__ == "__main__":
    main()
