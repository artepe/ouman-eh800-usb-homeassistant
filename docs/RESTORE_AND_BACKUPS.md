# Controller recovery and backups

The original Home Assistant integration on the user's EH-800B had a
`ouman_eh800.restore_original` service. Its source is included in
`custom_components/ouman_eh800/restore.py` in the review branch.
The service is **registered but never run automatically**.

## Before considering a restore

1. Have the **known-good** `/config/ouman_properties.txt` from the
   **same** controller; the capture used by the original restore had
   **269 unique property IDs**.
2. Back up the current Home Assistant configuration and verify the
   backup is readable.
3. Ensure the heating installation is being supervised and that you
   can safely stop the process and control the valve locally.
4. Check the snapshot's provenance and timestamp. Do not substitute
   generic defaults or someone else's dump.
5. The restore service accepts a minimum of 250 properties, but that
   threshold alone is **not proof of integrity or compatibility**.
   Inspect the snapshot independently before any restore.

## How the original action works

With top-level YAML config `ouman_eh800: {port: ...}`, the integration
registers `ouman_eh800.restore_original` in Developer Tools → Actions.
Manual invocation sends `SET PROPERTY <id> <raw>` for every
matching snapshot property via the legacy serial driver and reports
progress as `OUMAN RESTORE ...` in HA logs.

**WARNING:** This writes even PID properties. It is intentionally
not governed by the normal production PID read-only UI.
It is a destructive recovery operation, not a routine settings refresh.
The original implementation has no dry-run, transactional rollback, or
automated proof that controller state matches all requested values.
Keep power and USB connected. Do **not** call it as a test.

## Open data vs per-device settings

Source code, protocol notes, parsers and example fixtures are public.
Actual raw backups (`ouman_properties.txt`, `objects.dat`), firmware
images and unique device identifiers are **not** bundled in GitHub;
they have not been provided as publishable, verified anonymized copies.
Use `tools/capture_raw_usb.py` locally and inspect exports first.
