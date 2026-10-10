#!/usr/bin/env python3
"""Standalone read-only Ouman EH-800 USB example, no Home Assistant needed."""
import argparse
import asyncio

from ouman_eh800_usb_protocol import AsyncOumanUSB


async def run(port):
    client = AsyncOumanUSB(port)
    try:
        values = await client.measurements()
        for index, (value, unit) in enumerate(values, 1):
            print(f"{index:02d}: {value} {unit}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    asyncio.run(run(parser.parse_args().port))
