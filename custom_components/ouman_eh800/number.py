from __future__ import annotations
import voluptuous as vol
from homeassistant.components.number import PLATFORM_SCHEMA, NumberEntity
import homeassistant.helpers.config_validation as cv
from .const import DEFAULT_PORT
from .ouman import OumanUSB

CONF_PORT = "port"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string
})

# id, label, min raw, max raw, step raw, display scale, initial raw
# Only high-confidence L1 controls are writable in v0.1.
PROPS = [
    (54, "L1 Supply minimum", 50, 950, 10, 10, 140),
    (55, "L1 Supply maximum", 50, 950, 10, 10, 890),
    (56, "L1 P band", 2, 600, 1, 1, 250),
    (57, "L1 I time", 5, 300, 1, 1, 50),
    (58, "L1 D time", 0, 100, 1, 1, 0),
    (67, "L1 Curve -20C", 0, 1000, 10, 10, 900),
    (69, "L1 Curve -10C", 0, 1000, 10, 10, 700),
    (71, "L1 Curve 0C", 0, 1000, 10, 10, 550),
    (73, "L1 Curve +10C", 0, 1000, 10, 10, 490),
    (75, "L1 Curve +20C", 0, 1000, 10, 10, 180),
    (91, "L1 Summer shutoff", 5, 95, 1, 1, 24),
    (92, "L1 Manual valve position", 0, 100, 1, 1, 81),
    (126, "L1 Max supply change rate", 1, 50, 1, 1, 40),
    (127, "L1 Supply setpoint", 0, 950, 10, 10, 150),
    (134, "L1 Fine adjustment", -40, 40, 1, 10, 0),
]

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    hub = OumanUSB(config[CONF_PORT])
    async_add_entities([OumanNumber(hub, *p) for p in PROPS])

class OumanNumber(NumberEntity):
    _attr_should_poll = False

    def __init__(self, hub, pid, label, pmin, pmax, step, scale, initial):
        self.hub = hub
        self.pid = pid
        self.scale = scale
        self._attr_name = f"Ouman {label}"
        self._attr_unique_id = f"ouman_eh800_property_{pid}"
        self._attr_native_min_value = pmin / scale
        self._attr_native_max_value = pmax / scale
        self._attr_native_step = step / scale
        self._attr_native_value = initial / scale
        if scale == 10:
            self._attr_native_unit_of_measurement = "°C"

    async def async_set_native_value(self, value):
        raw = int(round(float(value) * self.scale))
        # EH-800 represents negative signed 16-bit property writes as uint16.
        wire_raw = raw & 0xFFFF
        _, _, _, _, returned = await self.hass.async_add_executor_job(
            self.hub.property, self.pid, wire_raw
        )
        signed_returned = returned - 65536 if returned >= 32768 else returned
        self._attr_native_value = signed_returned / self.scale
        self.async_write_ha_state()
