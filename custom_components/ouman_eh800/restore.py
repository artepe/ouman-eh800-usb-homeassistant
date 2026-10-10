"""Manual restore service preserved from the user's working EH-800B installation.

This is an EXCEPTIONAL recovery path; unlike regular PID sensors, it may write
PID values from the controller's own saved backup. Never invoke automatically.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DEFAULT_PORT, DOMAIN
from .ouman import OumanUSB

_LOGGER = logging.getLogger(__name__)

BASELINE_FILE = Path("/config/ouman_properties.txt")
BASELINE_RE = re.compile(
    r"PROPERTY\(\s*(\d+)\s*\):'[^']+'\([^)]*\)\s*=\s*(-?\d+)",
    re.I,
)
_restore_task = None


def _load_baseline():
    text = BASELINE_FILE.read_text(encoding="utf-8", errors="replace")
    props = {}
    for match in BASELINE_RE.finditer(text):
        props[int(match.group(1))] = int(match.group(2))
    return sorted(props.items())


async def async_setup_restore(hass: HomeAssistant, config: dict) -> bool:
    """Register, but never automatically call, restore_original."""
    conf = config.get(DOMAIN, {}) or {}
    port = conf.get("port", DEFAULT_PORT)
    hub = OumanUSB(port)

    async def restore_worker():
        global _restore_task
        try:
            props = await hass.async_add_executor_job(_load_baseline)
            if len(props) < 250:
                _LOGGER.error("OUMAN RESTORE ABORTED: only %s properties found", len(props))
                return
            _LOGGER.warning("OUMAN RESTORE START: %s properties", len(props))
            ok = 0
            failed = 0
            for index, (prop_id, value) in enumerate(props, 1):
                try:
                    result = await hass.async_add_executor_job(
                        hub.property, prop_id, value
                    )
                    ok += 1
                    if index == 1 or index % 10 == 0 or index == len(props):
                        _LOGGER.warning(
                            "OUMAN RESTORE %s/%s property=%s value=%s returned=%s",
                            index, len(props), prop_id, value, result[4],
                        )
                except Exception as err:
                    failed += 1
                    _LOGGER.error(
                        "OUMAN RESTORE FAILED %s/%s property=%s value=%s: %s",
                        index, len(props), prop_id, value, err,
                    )
            _LOGGER.warning("OUMAN RESTORE DONE: ok=%s failed=%s", ok, failed)
        finally:
            _restore_task = None

    async def handle_restore(call: ServiceCall):
        global _restore_task
        if _restore_task is not None and not _restore_task.done():
            _LOGGER.warning("OUMAN RESTORE already running")
            return
        _restore_task = hass.async_create_task(restore_worker())

    hass.services.async_register(DOMAIN, "restore_original", handle_restore)
    return True
