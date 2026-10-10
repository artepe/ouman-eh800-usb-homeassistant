#!/usr/bin/env python3
"""High-risk bench-only Ouman EH-800 USB property console.

NOT used by Home Assistant; no background writes and no firmware flashing.
Only runs against a controller explicitly connected to this computer.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys
import time

PROPERTY_LINE = re.compile(
    r"PROPERTY\(\s*(\d+)\s*\):'[^']+'\([^)]*\)\s*=\s*(-?\d+)"
)
PROPERTY_REPLY = re.compile(
    r"PROPERTY\(\s*(\d+)\s*\):'[^']+'\([^)]*\)\s*=\s*(-?\d+)"
)
ALLOWED_READ_COMMANDS = ("MEASUREMENTS", "LIST", "DEVINFO", "OSINFO", "TIME")
CONFIRM_PHRASE = "I_ACCEPT_CONTROLLER_DAMAGE_RISK"
PID_IDS = {56, 57, 58}


def checked_snapshot(path: Path) -> tuple[dict[int, int], str]:
    """Check that a backup is a plausible complete property snapshot."""
    if not path.is_file():
        raise ValueError("Snapshot file not found")
    content = path.read_bytes()
    if len(content) > 1024 * 1024:
        raise ValueError("Snapshot too large")
    decoded = content.decode("latin1")
    properties = {
        int(m.group(1)): int(m.group(2))
        for m in PROPERTY_LINE.finditer(decoded)
    }
    if len(properties) < 250:
        raise ValueError(
            f"Only {len(properties)} unique properties in snapshot; expected 250+"
        )
    return properties, sha256(content).hexdigest()


def encode_write(prop_id: int, raw: int) -> bytes:
    """Build a single property-write request without transmitting it."""
    if not 0 <= prop_id <= 65535:
        raise ValueError("Invalid property ID")
    if not -32768 <= raw <= 65535:
        raise ValueError("Raw integer outside accepted 16-bit encoding")
    return f"SET PROPERTY {prop_id} {raw & 0xFFFF}\n".encode("ascii")


def request(port: str, payload: bytes, deadline: float = 8) -> bytes:
    """Send one request. Diagnostic read; not a firmware transport."""
    import serial
    with serial.Serial(port, timeout=0.2, write_timeout=2, exclusive=True) as link:
        time.sleep(0.06)
        link.reset_input_buffer()
        link.write(payload)
        link.flush()
        chunks = []
        started = time.monotonic()
        last_data = None
        while time.monotonic() - started < deadline:
            chunk = link.read(4096)
            if chunk:
                chunks.append(chunk)
                last_data = time.monotonic()
            elif last_data is not None and time.monotonic() - last_data > 0.75:
                break
        return b"".join(chunks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    sub = parser.add_subparsers(dest="mode", required=True)
    rd = sub.add_parser("read", help="read-only, supported commands")
    rd.add_argument("command", choices=ALLOWED_READ_COMMANDS)
    wr = sub.add_parser("write", help="one high-risk property write, never batch")
    wr.add_argument("property_id", type=int)
    wr.add_argument("raw_value", type=int)
    wr.add_argument("--snapshot", required=True, type=Path)
    wr.add_argument("--confirm", default="")
    wr.add_argument("--allow-pid", action="store_true")
    wr.add_argument("--allow-unbacked", action="store_true")
    args = parser.parse_args()

    if args.mode == "read":
        payload = (args.command + "\n").encode("ascii")
        answer = request(args.port, payload)
    else:
        if args.confirm != CONFIRM_PHRASE:
            parser.error("Refusing dangerous write: provide explicit --confirm phrase")
        properties, digest = checked_snapshot(args.snapshot)
        if args.property_id not in properties and not args.allow_unbacked:
            parser.error("Property not in your backup; requires --allow-unbacked")
        if args.property_id in PID_IDS and not args.allow_pid:
            parser.error("PID 56/57/58 are known-risk; requires --allow-pid")
        payload = encode_write(args.property_id, args.raw_value)
        print(f"Snapshot SHA256: {digest}", file=sys.stderr)
        print("You must verify this backup belongs to THIS controller.", file=sys.stderr)
        print("WARNING: unexpected valve movement / water temperatures possible.", file=sys.stderr)
        print("Never use this command with a running unattended heating system.", file=sys.stderr)
        typed = input(f"Type WRITE {args.property_id} to transmit ONE command: ")
        if typed != f"WRITE {args.property_id}":
            parser.error("No write sent; second confirmation failed")
        answer = request(args.port, payload)

    print("TX HEX:", payload.hex(" "))
    print("RX HEX:", answer.hex(" "))
    print("RX TEXT:", answer.decode("latin1", errors="replace"))
    if args.mode == "write":
        found = PROPERTY_REPLY.search(answer.decode("latin1", errors="replace"))
        expected = args.raw_value & 0xFFFF
        if not found or int(found.group(1)) != args.property_id or int(found.group(2)) not in (expected, args.raw_value):
            raise RuntimeError(
                "No matching property acknowledgement. DO NOT resend blindly; "
                "check device physical state and logs."
            )
        print("ACK matched the requested property and raw value.")
        print("Physical controller screen may stay stale: ESC then reopen settings.")


if __name__ == "__main__":
    main()
