from __future__ import annotations
import voluptuous as vol
from homeassistant.components.number import PLATFORM_SCHEMA, NumberEntity
from homeassistant.helpers.entity import DeviceInfo
import homeassistant.helpers.config_validation as cv
from .const import DEFAULT_PORT, DOMAIN
from .ouman import OumanUSB

CONF_PORT = "port"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string})

from .control_definitions import WRITABLE_PROPS

# All original non-PID controls retain the same legacy IDs and write path.
# PID settings 56/57/58 deliberately have no writable Number entities.
PROPS = WRITABLE_PROPS

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    hub = OumanUSB(config[CONF_PORT])
    async_add_entities([OumanNumber(hub, *p) for p in PROPS])

class OumanNumber(NumberEntity):
    _attr_should_poll = False

    def __init__(self, hub, pid, object_id, label, pmin, pmax, step, scale, initial):
        self.hub = hub
        self.pid = pid
        self.scale = scale
        self._attr_name = f"Ouman {label}"
        self._attr_object_id = f"ouman_{object_id}"
        self._attr_unique_id = f"ouman_eh800_property_{pid}"
        self._attr_native_min_value = pmin / scale
        self._attr_native_max_value = pmax / scale
        self._attr_native_step = step / scale
        self._attr_native_value = initial / scale
        if scale == 10:
            self._attr_native_unit_of_measurement = "°C"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, "eh800_usb")},
            name="Ouman EH-800B",
            manufacturer="Ouman",
            model="EH-800 / EH-800B",
        )

    async def async_set_native_value(self, value):
        raw = int(round(float(value) * self.scale))
        wire_raw = raw & 0xFFFF
        _, _, _, _, returned = await self.hass.async_add_executor_job(self.hub.property, self.pid, wire_raw)
        signed_returned = returned - 65536 if returned >= 32768 else returned
        self._attr_native_value = signed_returned / self.scale
        self.async_write_ha_state()


# New opt-in UI-configured controls. The historical YAML class above and its
# acknowledged SET PROPERTY write path are intentionally unchanged, except that
# PID properties 56/57/58 are not included in PROPS.
async def async_setup_entry(hass, entry, async_add_entities):
    """Add all non-PID controls using the shared asynchronous USB session."""
    client, _ = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        OumanEntryNumber(client, entry.entry_id, *prop) for prop in PROPS
    )


class OumanEntryNumber(NumberEntity):
    """One verified, range-checked SET PROPERTY request per adjustment.

    The protocol has no confirmed side-effect-free live property getter yet.
    Startup values therefore remain unknown rather than using misleading
    baked-in defaults or silently writing to read them.
    """

    _attr_should_poll = False

    def __init__(self, client, entry_id, pid, object_id, label,
                 pmin, pmax, step, scale, initial):
        from homeassistant.components.number import NumberMode

        self.client = client
        self.entry_id = entry_id
        self.pid = pid
        self.scale = scale
        self.raw_min = pmin
        self.raw_max = pmax
        self.raw_step = step
        self._attr_name = f"Ouman {label}"
        self._attr_unique_id = f"ouman_eh800_{entry_id}_property_{pid}"
        self._attr_object_id = f"ouman_{object_id}"
        self._attr_native_min_value = pmin / scale
        self._attr_native_max_value = pmax / scale
        self._attr_native_step = step / scale
        self._attr_native_value = None
        # A box can accept input when the device's present value is unknown.
        self._attr_mode = NumberMode.BOX
        self._attr_extra_state_attributes = {
            "readback": "not_available",
            "value_source": "unknown_until_acknowledged_write",
        }
        if scale == 10:
            self._attr_native_unit_of_measurement = "°C"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, f"eh800_usb_{self.entry_id}")},
            name="Ouman EH-800 / EH-800B USB",
            manufacturer="Ouman",
            model="EH-800 / EH-800B",
        )

    async def async_set_native_value(self, value: float) -> None:
        if self.pid in (56, 57, 58):
            raise ValueError("PID control parameters are read-only")
        raw = int(round(float(value) * self.scale))
        if (
            raw < self.raw_min
            or raw > self.raw_max
            or (raw - self.raw_min) % self.raw_step
            or abs(raw / self.scale - float(value)) > 0.000001
        ):
            raise ValueError(
                f"Invalid value {value} for Ouman property {self.pid}"
            )

        reply = await self.client.set_property(self.pid, raw)
        actual_raw = (
            reply.raw_value - 65536
            if 32768 <= reply.raw_value <= 65535
            else reply.raw_value
        )
        self._attr_native_value = actual_raw / self.scale
        self._attr_extra_state_attributes = {
            "readback": "acknowledged_write_only",
            "value_source": "last_acknowledged_set_property",
        }
        self.async_write_ha_state()
