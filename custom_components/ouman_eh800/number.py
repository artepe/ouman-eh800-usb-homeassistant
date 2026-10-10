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
