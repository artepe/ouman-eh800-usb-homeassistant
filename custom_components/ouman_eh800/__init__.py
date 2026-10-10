"""Ouman EH-800 / EH-800B USB Home Assistant integration.

Existing YAML sensor/number platforms remain supported; only PID Number writes are disabled.
The optional config-entry path uses the isolated async protocol client.
"""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN
from .usb_protocol import AsyncOumanUSB

_LOGGER = logging.getLogger(__name__)
PLATFORMS = (Platform.SENSOR, Platform.NUMBER)
SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_entry(hass, entry) -> bool:
    """Set up opt-in UI entry with readings and non-PID controls."""
    port = entry.data[CONF_DEVICE]
    client = AsyncOumanUSB(port)

    async def _async_update():
        try:
            return await client.measurements()
        except (OSError, ConnectionError, TimeoutError, RuntimeError, ValueError) as err:
            raise UpdateFailed(f"Ouman EH-800 USB read failed: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Ouman EH-800 USB measurements",
        update_method=_async_update,
        update_interval=SCAN_INTERVAL,
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        await client.disconnect()
        raise ConfigEntryNotReady(f"Unable to read Ouman at {port}: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = (client, coordinator)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await client.disconnect()
        raise
    return True


async def async_unload_entry(hass, entry) -> bool:
    """Release the serial port when an entry is unloaded."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime:
        await runtime[0].disconnect()
    return True
