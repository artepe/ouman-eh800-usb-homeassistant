from __future__ import annotations
from datetime import timedelta
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from .const import DEFAULT_PORT
from .ouman import OumanUSB

CONF_PORT = "port"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default="Ouman EH-800"): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
})
SCAN_INTERVAL = timedelta(seconds=15)

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
    async_add_entities(
        [OumanMeasurement(hub, i, NAMES.get(i, f"Measurement {i}")) for i in range(1, 29)],
        True,
    )

class OumanMeasurement(SensorEntity):
    _attr_should_poll = True

    def __init__(self, hub, index, name):
        self.hub = hub
        self.index = index
        self._attr_name = f"Ouman {name}"
        self._attr_unique_id = f"ouman_eh800_measurement_{index}"
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = None

    async def async_update(self):
        vals = await self.hass.async_add_executor_job(self.hub.measurements)
        if len(vals) >= self.index:
            value, unit = vals[self.index - 1]
            self._attr_native_value = value
            self._attr_native_unit_of_measurement = "°C" if unit.lower() == "c" else unit
