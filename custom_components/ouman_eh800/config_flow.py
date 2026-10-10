"""Opt-in UI setup and USB discovery; legacy YAML remains supported."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.helpers.selector import SerialPortSelector
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import DOMAIN
from .usb_protocol import AsyncOumanUSB

_LOGGER = logging.getLogger(__name__)
DATA_SCHEMA = vol.Schema({vol.Required(CONF_DEVICE): SerialPortSelector()})


async def _probe(port: str) -> bool:
    """Validate a full measurement response before creating an entry."""
    client = AsyncOumanUSB(port)
    try:
        await client.measurements()
        return True
    except (OSError, ConnectionError, TimeoutError, RuntimeError, ValueError):
        _LOGGER.warning("Failed to read Ouman EH-800 at %s", port, exc_info=True)
        return False
    finally:
        await client.disconnect()


class OumanEH800USBConfigFlow(ConfigFlow, domain=DOMAIN):
    """Serial-port setup; does not change existing YAML platform entries."""

    VERSION = 1
    _discovered_port: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            port = user_input[CONF_DEVICE]
            self._async_abort_entries_match({CONF_DEVICE: port})
            if await _probe(port):
                await self.async_set_unique_id(f"port:{port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Ouman EH-800 USB", data={CONF_DEVICE: port}
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Offer discovery only; never take over a running YAML installation."""
        self._discovered_port = discovery_info.device
        self._async_abort_entries_match({CONF_DEVICE: self._discovered_port})
        await self.async_set_unique_id(f"port:{self._discovered_port}")
        self._abort_if_unique_id_configured()
        return await self.async_step_usb_confirm()

    async def async_step_usb_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require explicit confirmation before probing the port."""
        if user_input is None:
            return self.async_show_form(
                step_id="usb_confirm",
                data_schema=vol.Schema({}),
                description_placeholders={"port": self._discovered_port or ""},
            )
        assert self._discovered_port is not None
        if not await _probe(self._discovered_port):
            return self.async_show_form(
                step_id="usb_confirm",
                data_schema=vol.Schema({}),
                errors={"base": "cannot_connect"},
                description_placeholders={"port": self._discovered_port},
            )
        return self.async_create_entry(
            title="Ouman EH-800 USB",
            data={CONF_DEVICE: self._discovered_port},
        )
