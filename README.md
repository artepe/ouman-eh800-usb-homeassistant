# Ouman EH-800 USB → Home Assistant

Independent reverse-engineering project for local USB CDC communication with Ouman EH-800/EH-800B controllers.

**Author:** Petteri Miikkael Arte  
**Copyright © 2026 Petteri Miikkael Arte**  
**License:** MIT

Not affiliated with or endorsed by Ouman Oy.

## What works in v0.1.2

- USB CDC serial connection (tested device VID:PID `eb03:0920`)
- `MEASUREMENTS` polling into 28 Home Assistant sensor entities
- Confirmed configuration writes with `SET PROPERTY <id> <value>`
- Safe first set of L1 controls as Home Assistant Number entities
- Shared per-port USB locking and property-write retries
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

Restart Home Assistant after validating the configuration.

## Restoring a previously saved EH-800 property snapshot

This recovery procedure is being hardware-tested on an EH-800B during reverse engineering. During the current restore of a previously captured 269-property snapshot, the normal line between the five L1 heating-curve points returned on the physical EH-800 display while the restore was still in progress.

### Important safety notes

The restore writes live controller configuration. Use only a snapshot captured from the **same controller**.

The project does not contain universal factory defaults and does not guess missing values. Do not use another controller's property dump as a factory-reset file.

Do not restart Home Assistant, disconnect USB, power-cycle the EH-800, or change settings from the physical controller while a restore is running.

### Required backup file

Keep the known-good property snapshot at:

```text
/config/ouman_properties.txt
```

The tested file contains records in this format:

```text
PROPERTY(67):'L1_KAYRAN_MENOVESI_5A'(0-1000) = 900
PROPERTY(73):'L1_KAYRAN_MENOVESI_5D'(0-1000) = 490
```

Before restoring, verify the number of unique properties:

```bash
grep -oE 'PROPERTY\([0-9]+\)' /config/ouman_properties.txt | sort -u | wc -l
```

The tested full snapshot contained **269 unique properties**. Do not continue with a clearly incomplete file.

### Enable the restore helper

The currently tested development restore helper is loaded from the integration's `async_setup` and registers:

```text
ouman_eh800.restore_original
```

The integration must therefore also have a top-level configuration entry:

```yaml
ouman_eh800:
  port: /dev/serial/by-id/usb-OUMAN_Ouman_EH-800-if00
```

After installing the restore-enabled development version, validate first:

```bash
ha core check
```

Continue only when Home Assistant reports:

```text
Command completed successfully.
```

Then restart Home Assistant:

```bash
ha core restart
```

### Start the restore

Open **Developer Tools → Actions** and search for:

```text
ouman_eh800.restore_original
```

Run the action **once**.

Do not use an unauthenticated Terminal `curl` call as a substitute. In testing, the Supervisor/Core API request returned HTTP 401, while running the registered action from Home Assistant Developer Tools worked correctly.

### Follow progress

Open Terminal & SSH and run:

```bash
ha core logs -f | grep "OUMAN RESTORE"
```

A normal restore looks like:

```text
OUMAN RESTORE START: 269 properties
OUMAN RESTORE 1/269 property=1 value=65491 returned=65491
OUMAN RESTORE 10/269 ...
OUMAN RESTORE 20/269 ...
...
OUMAN RESTORE 269/269 ...
OUMAN RESTORE DONE: ok=269 failed=0
```

Values such as `65491` can be the unsigned 16-bit representation of a negative signed setting and are not automatically an error.

The desired final result is:

```text
OUMAN RESTORE DONE: ok=269 failed=0
```

If `failed` is not zero, do not repeatedly rerun the full restore. Check the preceding `OUMAN RESTORE FAILED` lines and identify the affected property IDs first.

### Verify the physical controller

After the restore has finished, verify important settings directly from the EH-800 display before relying on automatic operation:

- L1 heating curve and all five curve points
- supply-water minimum and maximum limits
- controller operating mode
- valve/motor operation
- installation-specific relay, network and hybrid settings

During the current hardware recovery, the L1 curve line visibly returned before the complete 269-property restore had finished. The restore was left running and should not be interrupted before the final `DONE` line.

### Keep recovery copies

Keep known-good recovery files outside the live controller. During development, both a property snapshot and an original `objects.dat` image were retained before further reverse engineering.

The property restore is not a firmware flash. The controller's `FIRMWARE` command is intentionally not used.

## Important

Writing properties changes the live heating controller configuration. v0.1 exposes only high-confidence L1 controls mapped during hardware testing.

Known service-shell commands include `MEASUREMENTS`, `LIST`, `TYPE`, `KEYECHO`, `OSINFO`, `DEVINFO`, `TIME`, `SET CLOCK`, `SET DATE`, `SET DAY`, `RENAME`, `FIRMWARE`, `PTESTER`, and `SET PROPERTY variable value`.

The `FIRMWARE` path is intentionally not implemented.
