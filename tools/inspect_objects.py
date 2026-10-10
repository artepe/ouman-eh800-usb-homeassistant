#!/usr/bin/env python3
"""Read-only offline hex inspection of a local 3192-byte objects.dat backup."""
import argparse
from pathlib import Path

SIZE = 3192
CURVE = {-20: 2536, -10: 2556, 0: 2576, 10: 2596, 20: 2616}
FINE = 2776


def inspect_data(data):
    if len(data) != SIZE:
        raise ValueError(f"Expected {SIZE} bytes from research sample; got {len(data)}")
    result = []
    for ambient, offset in CURVE.items():
        raw_y = int.from_bytes(data[offset:offset + 2], "little")
        raw_x = int.from_bytes(data[offset + 10:offset + 12], "little", signed=True)
        result.append((ambient, offset, raw_y / 10, raw_x / 10, data[offset:offset + 12].hex(" ")))
    fine = int.from_bytes(data[FINE:FINE + 1], "little", signed=True) / 10
    return result, fine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path, help="Private saved objects.dat image")
    args = parser.parse_args()
    result, fine = inspect_data(args.file.read_bytes())
    for ambient, offset, water, outdoor, raw_hex in result:
        print(f"{ambient:+3d} C: offset={offset} supply={water:.1f} C stored-X={outdoor:+.1f} C hex={raw_hex}")
    print(f"fine adjustment offset={FINE}: {fine:+.1f} C")
    print("Research offsets: one EH-800B case, not universal. No writes performed.")


if __name__ == "__main__":
    main()
