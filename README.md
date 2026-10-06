# Ouman EH-800 USB → Home Assistant

Independent reverse-engineering project for local USB CDC communication with Ouman EH-800/EH-800B controllers.

**Author:** Petteri Miikkael Arte  
**Copyright © 2026 Petteri Miikkael Arte**  
**License:** MIT

Not affiliated with or endorsed by Ouman Oy.

## What works in v0.1.0

- USB CDC serial connection (tested device VID:PID `eb03:0920`)
- `MEASUREMENTS` polling into 28 Home Assistant sensor entities
- Confirmed configuration writes with `SET PROPERTY <id> <value>`
- Safe first set of L1 controls as Home Assistant Number entities
- Stable tested Linux device path: `/dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00`

Confirmed write example: `SET PROPERTY 67 910` changed the L1 -20 °C curve point from 90.0 °C to 91.0 °C on the physical controller.

## Home Assistant OS

Copy `custom_components/ouman_eh800` to `/config/custom_components/ouman_eh800`.

Add:

```yaml
sensor:
  - platform: ouman_eh800
    port: /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00

number:
  - platform: ouman_eh800
    port: /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00
```

Restart Home Assistant.

## Important

Writing properties changes the live heating controller configuration. v0.1 exposes only high-confidence L1 controls mapped during hardware testing.

Known service-shell commands include `MEASUREMENTS`, `LIST`, `TYPE`, `KEYECHO`, `OSINFO`, `DEVINFO`, `TIME`, `SET CLOCK`, `SET DATE`, `SET DAY`, `RENAME`, `FIRMWARE`, `PTESTER`, and `SET PROPERTY variable value`.

The `FIRMWARE` path is intentionally not implemented.
