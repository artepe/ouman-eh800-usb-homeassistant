from __future__ import annotations
from datetime import timedelta
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.helpers.entity import DeviceInfo
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from .const import DEFAULT_PORT, DOMAIN
from .control_definitions import PID_PROPS, load_property_snapshot
from .ouman import OumanUSB

CONF_PORT = "port"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
})
SCAN_INTERVAL = timedelta(seconds=1)  # Preserve tested user's legacy YAML polling

NAMES = {
    1: "L1 calculated supply target",
    7: "L1 calculated supply target 2",
    9: "L1 supply water temperature",
    10: "Outdoor temperature",
    11: "Outdoor temperature adjusted",
    15: "L1 valve calculated position",
    16: "L1 valve position",
    19: "Measurement 19",
    20: "Measurement 20",
    21: "Delayed outdoor temperature",
    27: "Measurement 27",
    28: "Digital input",
}

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    hub = OumanUSB(config[CONF_PORT])

    async def _update():
        return await hass.async_add_executor_job(hub.measurements)

    coordinator = DataUpdateCoordinator(
        hass,
        logger=__import__("logging").getLogger(__name__),
        name="Ouman EH-800 measurements",
        update_method=_update,
        update_interval=SCAN_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()
    async_add_entities(
        [
            OumanMeasurement(coordinator, i, NAMES.get(i, f"Measurement {i}"))
            for i in range(1, 29)
        ]
        + [
            OumanPIDSnapshotSensor(hass.config.path("ouman_properties.txt"), p)
            for p in PID_PROPS
        ]
    )

class OumanMeasurement(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, index, name):
        super().__init__(coordinator)
        self.index = index
        self._attr_name = f"Ouman {name}"
        self._attr_unique_id = f"ouman_eh800_measurement_{index}"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, "eh800_usb")},
            name="Ouman EH-800B",
            manufacturer="Ouman",
            model="EH-800 / EH-800B",
        )

    @property
    def native_value(self):
        vals = self.coordinator.data or []
        return vals[self.index - 1][0] if len(vals) >= self.index else None

    @property
    def native_unit_of_measurement(self):
        vals = self.coordinator.data or []
        if len(vals) < self.index:
            return None
        unit = vals[self.index - 1][1]
        return "°C" if unit.lower() == "c" else unit


# The optional UI flow uses a separate async coordinator. The original
# YAML async_setup_platform above is preserved byte-for-byte.
async def async_setup_entry(hass, entry, async_add_entities):
    """Create read-only measurement entities from the serialx coordinator."""
    _, coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            OumanEntryMeasurement(
                coordinator, i, NAMES.get(i, f"Measurement {i}"), entry.entry_id
            )
            for i in range(1, 29)
        ]
        + [
            OumanPIDSnapshotSensor(
                hass.config.path("ouman_properties.txt"), p, entry.entry_id
            )
            for p in PID_PROPS
        ]
    )


class OumanEntryMeasurement(OumanMeasurement):
    """Entry-specific IDs avoid collisions with the legacy YAML entities."""

    def __init__(self, coordinator, index, name, entry_id):
        super().__init__(coordinator, index, name)
        self._entry_id = entry_id
        self._attr_unique_id = f"ouman_eh800_{entry_id}_measurement_{index}"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, f"eh800_usb_{self._entry_id}")},
            name="Ouman EH-800 / EH-800B USB",
            manufacturer="Ouman",
            model="EH-800 / EH-800B",
        )


class OumanPIDSnapshotSensor(SensorEntity):
    """Read a previously saved controller backup, NEVER the live PID register.

    The EH-800 USB shell has no validated no-write GET PROPERTY command.
    This entity is explicitly named and attributed as a stored snapshot.
    """

    _attr_should_poll = True

    def __init__(self, snapshot_path, prop, entry_id=None):
        self.snapshot_path = snapshot_path
        self.pid, object_id, label, pmin, pmax, step, scale, initial = prop
        self.scale = scale
        self.entry_id = entry_id
        self._attr_name = f"Ouman {label} (saved snapshot)"
        if entry_id is None:
            self._attr_unique_id = f"ouman_eh800_saved_pid_{self.pid}"
        else:
            self._attr_unique_id = f"ouman_eh800_{entry_id}_saved_pid_{self.pid}"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {
            "data_source": "saved_backup_file_not_live",
            "source_file": "ouman_properties.txt",
            "live": False,
        }

    @property
    def device_info(self):
        identifier = (
            f"eh800_usb_{self.entry_id}" if self.entry_id else "eh800_usb"
        )
        return DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name="Ouman EH-800 / EH-800B USB",
            manufacturer="Ouman",
            model="EH-800 / EH-800B",
        )

    async def async_update(self):
        """Load only from the saved file, without any USB command."""
        from datetime import datetime, timezone
        from pathlib import Path

        def _read():
            path = Path(self.snapshot_path)
            values = load_property_snapshot(path)
            return values.get(self.pid), (
                datetime.fromtimestamp(
                    path.stat().st_mtime, timezone.utc
                ).isoformat() if path.is_file() else None
            )

        try:
            raw, file_modified = await self.hass.async_add_executor_job(_read)
        except (OSError, ValueError) as err:
            raw = file_modified = None
            self._attr_extra_state_attributes = {
                "data_source": "saved_backup_file_not_live",
                "source_file": "ouman_properties.txt",
                "live": False,
                "read_error": str(err),
            }
        else:
            self._attr_extra_state_attributes = {
                "data_source": "saved_backup_file_not_live",
                "source_file": "ouman_properties.txt",
                "live": False,
                "file_modified_utc": file_modified,
            }
        self._attr_native_value = raw / self.scale if raw is not None else None
