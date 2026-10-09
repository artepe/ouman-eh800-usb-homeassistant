# Ouman EH-800 / EH-800B USB protocol library (experimental)

This is **stage 1 of the migration**, not a replacement Home Assistant integration.

It separates the serial protocol from Home Assistant and uses the async
`serialx` API, supporting local serial paths and `socket://` endpoints on the
same code path. ESPHome serial proxy is a future compatibility target.

Features:
- One persistent serial connection per client.
- `asyncio.Lock` around every request/response.
- Complete 28-record `MEASUREMENTS` responses across arbitrary read chunks.
- Explicit matching `PROPERTY(id)` response framing for writes.
- Disconnect/reconnect on the next operation after errors.
- No automatic retry of writes: if the response is lost, a write might have
  succeeded and must **not** be resent blindly.
- No Home Assistant imports.

**Hardware validation is still required.** The framing assumes exactly 28
measurement lines with newline terminators. Capture actual bytes from both
EH-800 and EH-800B and adjust the frame parser if either firmware varies.
Do not publish to PyPI or switch the working integration to this transport
until the hardware tests pass.

## Local install and tests

```bash
cd protocol
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

## Example: read measurements

```python
import asyncio
from ouman_eh800_usb_protocol import OumanUSBClient

async def main():
    async with OumanUSBClient(
        "/dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00"
    ) as ouman:
        values = await ouman.measurements()
        print(values)

asyncio.run(main())
```

## Serial server (LAN-only)

You can eventually test through a private network serial bridge using
`socket://<trusted-lan-host>:4001`. This is an **unencrypted** connection:
never port-forward it to the internet or expose the heat controller outside
your trusted LAN. Verify the serial device path on the proxy host first.

Only one client may own the Ouman serial port at a time. Stop the existing
Home Assistant legacy polling integration before running the hardware test.

The library intentionally does not provide a public API for unsafe PID writes,
firmware updates, or bulk-restoring properties. Its low-level explicit property
write accepts a raw ID and value; a future HA integration must allowlist
only hardware-validated, safe, range-checked writable properties.
