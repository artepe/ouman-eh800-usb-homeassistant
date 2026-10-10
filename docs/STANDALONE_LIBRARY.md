# Use the USB protocol outside Home Assistant

The reverse-engineered serialx client is deliberately independent of HA.
It lives in `custom_components/ouman_eh800/usb_protocol`, with
`pyproject.toml` at the repository root. It is source-available under MIT
and has not been published on PyPI.

```bash
git clone https://github.com/artepe/ouman-eh800-usb-homeassistant.git
cd ouman-eh800-usb-homeassistant
git checkout feat/usb-async-safe-config-20261010
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
python examples/standalone_read.py --port /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00
```

The `ouman_eh800_usb_protocol` Python package exposes
`AsyncOumanUSB`, `OumanProtocolError` and `PropertyReply`.
The reader returns a list of 28 value/unit tuples.

Use it on a computer that currently owns the USB serial port. The
Home Assistant integration, a diagnostic capture and a standalone
client must **not** open the same port simultaneously.

To create a raw diagnostic file without HA:
```bash
pip install pyserial==3.5
python tools/capture_raw_usb.py --port /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00 --command MEASUREMENTS --output raw_measurements.json
```

Logs include exact TX/RX byte sequences in HEX. The capture utility
uses a bounded quiet-period diagnostic read and is not a strict
production framing parser. It does not auto-upload any logs or backups.
