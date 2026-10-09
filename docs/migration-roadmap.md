# Planned non-breaking HA migration

Markus98 proposed isolating USB from HTTP and using serialx plus the USB
config-flow selector. The current YAML integration remains untouched in this
branch, so the live heating setup is not disturbed.

## Stage 1 (this branch)

- Independently installable `protocol/` Python package without HA imports.
- Async `serialx.open_serial_connection(url=...)`.
- Persistent transport, a single request lock, deterministic 28-record
  measurements and matching property replies.
- Fake serial tests including 256-byte proxy chunks.
- Initial network transport compatibility via `socket://`.
- Do **not** publish the package to PyPI until testing on real hardware.

## Stage 2 (after recorded hardware test)

- Verify actual framing for EH-800B and EH-800 variants with redacted captures.
- Read existing configuration without using writes. The current number platform
  uses static initial raw values; those must not be mistaken for device state.
  Do **not** use `SET PROPERTY` as a 'read' operation.
- Exclude PID 56/57/58 and other unverified settings from public write controls.
  Preserve known-good working L1 curve-point writes.
- Publish versioned protocol package to PyPI after CI + real hardware checks.

## Stage 3 (new parallel integration, not an in-place rename)

- Add `custom_components/ouman_eh_800_usb` with `config_flow: true`.
- `dependencies: ["usb"]`, `SerialPortSelector()`, `CONF_DEVICE`,
  and a USB match for EB03:0920 (validated on the actual controller).
- Keep the USB domain distinct from the official HTTP domain
  `ouman_eh_800` and from the legacy domain `ouman_eh800`.
- A single config-entry-owned client, one `DataUpdateCoordinator` and
  stable device-linked unique IDs, translations, and diagnostics.
- Read-only startup until successful readbacks and validation of safe writes.
- Add migrations / entity mapping before asking users to switch integrations.
  Never run legacy and new integrations on one controller concurrently.
- Test remote serial over `socket://` before ESPHome serial proxy testing.
- Add a rollback and cutover checklist for existing user installations.

## Capture request

To verify protocol terminators, collect the fully received raw ASCII bytes
of one `MEASUREMENTS` command and one harmless property response from an
isolated test machine. Avoid changing any live heating settings merely to
record traffic. Do not include personal information or network credentials.
