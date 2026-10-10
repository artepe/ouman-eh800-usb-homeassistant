"""Async Ouman EH-800 USB CDC-ACM client.

No Home Assistant dependencies. Async serialx supports local serial paths,
socket:// URLs, and serial-proxy transports supported by the host.

The controller's MEASUREMENTS response is treated as 28 line-based values.
This is based on the existing 28-sensor integration and MUST be validated
against captures from additional EH-800/EH-800B firmware revisions.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
from time import monotonic
from typing import Any, Callable

MEASUREMENT_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(C|%|dig)\s*$", re.IGNORECASE
)
PROPERTY_RE = re.compile(
    r"PROPERTY\(\s*(\d+)\s*\):'([^']+)'\([^)]*\)\s*=\s*(-?\d+)",
    re.IGNORECASE,
)

# Conservative, explicitly checked writable controls; not exposed by the new
# config-entry path. PID settings 56-58 and manual-valve position 92 are
# intentionally not allowed. Never restore arbitrary property dumps here.
SAFE_WRITABLE_RAW_RANGES = {
    54: (50, 950),    # Supply minimum, 0.1 C
    55: (50, 950),    # Supply maximum, 0.1 C
    67: (0, 1000),    # Heating curve -20 C
    69: (0, 1000),    # Heating curve -10 C
    71: (0, 1000),    # Heating curve   0 C
    73: (0, 1000),    # Heating curve +10 C
    75: (0, 1000),    # Heating curve +20 C
    91: (5, 95),      # Summer shutoff
    126: (1, 50),    # Max supply change rate
    127: (0, 950),   # Supply setpoint
    134: (-40, 40),  # Fine adjustment
}
MAX_RESPONSE_LINES = 128
MAX_RESPONSE_BYTES = 16384


class OumanProtocolError(RuntimeError):
    """Missing, truncated, or inconsistent response from the controller."""


@dataclass(frozen=True)
class PropertyReply:
    """Controller's acknowledgement to a property write."""

    property_id: int
    name: str
    raw_value: int


class AsyncOumanUSB:
    """A single persistent, lock-protected serial session."""

    def __init__(
        self,
        port: str,
        *,
        timeout: float = 9.0,
        expected_measurements: int = 28,
        connection_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.port = port
        self.timeout = timeout
        self.expected_measurements = expected_measurements
        self._connection_factory = connection_factory
        self._reader: Any = None
        self._writer: Any = None
        self._lock = asyncio.Lock()

    async def _connect_unlocked(self) -> None:
        if self._writer is not None:
            return
        factory = self._connection_factory
        if factory is None:
            from serialx import open_serial_connection

            factory = open_serial_connection
        # Keep the original URL unchanged: /dev/serial/..., socket:// or
        # an ESPHome proxy URL all belong to the serialx transport.
        self._reader, self._writer = await factory(url=self.port)

    async def connect(self) -> None:
        """Open one serial session; safe to call repeatedly."""
        async with self._lock:
            await self._connect_unlocked()

    async def _close_unlocked(self) -> None:
        writer = self._writer
        self._reader = None
        self._writer = None
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, ConnectionError):
                pass

    async def disconnect(self) -> None:
        """Close the transport after outstanding commands finish."""
        async with self._lock:
            await self._close_unlocked()

    async def _send_unlocked(self, command: str) -> None:
        await self._connect_unlocked()
        self._writer.write((command + "\n").encode("ascii"))
        await self._writer.drain()

    async def _read_line_unlocked(self, deadline: float) -> str:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise OumanProtocolError("Timed out waiting for EH-800 reply")
        try:
            line: bytes = await asyncio.wait_for(
                self._reader.readline(), timeout=remaining
            )
        except asyncio.TimeoutError as err:
            raise OumanProtocolError("Timed out waiting for EH-800 reply") from err
        if not line:
            raise OumanProtocolError("EH-800 connection closed before reply finished")
        if not line.endswith(b"\n"):
            raise OumanProtocolError("EH-800 returned an unterminated reply line")
        return line.decode("latin1", errors="replace").strip()

    async def measurements(self) -> list[tuple[float, str]]:
        """Read a complete 28-value measurement frame, never a partial frame."""
        async with self._lock:
            try:
                await self._send_unlocked("MEASUREMENTS")
                deadline = monotonic() + self.timeout
                values: list[tuple[float, str]] = []
                total = 0
                for _ in range(MAX_RESPONSE_LINES):
                    line = await self._read_line_unlocked(deadline)
                    total += len(line) + 1
                    if total > MAX_RESPONSE_BYTES:
                        raise OumanProtocolError("EH-800 response too large")
                    match = MEASUREMENT_RE.search(line)
                    if match:
                        values.append((float(match.group(1)), match.group(2)))
                        if len(values) == self.expected_measurements:
                            return values
                raise OumanProtocolError(
                    f"EH-800 reply contained only {len(values)} of "
                    f"{self.expected_measurements} measurements"
                )
            except BaseException:
                # A partial frame must never contaminate the next command.
                await self._close_unlocked()
                raise

    async def set_property(self, property_id: int, raw_value: int) -> PropertyReply:
        """Write only documented, range-checked properties; never retry writes.

        This method is library-only for now. The new HA config-entry path exposes
        sensors, not writable Number entities, until hardware tests are complete.
        """
        if type(property_id) is not int or type(raw_value) is not int:
            raise ValueError("Property ID and value must be integers")
        if property_id not in SAFE_WRITABLE_RAW_RANGES:
            raise ValueError(f"Property {property_id} is not allowed for writing")
        lower, upper = SAFE_WRITABLE_RAW_RANGES[property_id]
        if not lower <= raw_value <= upper:
            raise ValueError(f"Property {property_id} must be between {lower} and {upper}")
        wire_value = raw_value & 0xFFFF
        async with self._lock:
            try:
                await self._send_unlocked(f"SET PROPERTY {property_id} {wire_value}")
                deadline = monotonic() + self.timeout
                total = 0
                for _ in range(MAX_RESPONSE_LINES):
                    line = await self._read_line_unlocked(deadline)
                    total += len(line) + 1
                    if total > MAX_RESPONSE_BYTES:
                        raise OumanProtocolError("EH-800 property response too large")
                    match = PROPERTY_RE.search(line)
                    if not match:
                        continue
                    returned_id = int(match.group(1))
                    returned_raw = int(match.group(3))
                    if returned_id != property_id:
                        raise OumanProtocolError(
                            f"Controller answered property {returned_id}; "
                            f"expected {property_id}"
                        )
                    if returned_raw != wire_value and returned_raw != raw_value:
                        raise OumanProtocolError(
                            f"Controller returned {returned_raw}, expected {wire_value}"
                        )
                    return PropertyReply(returned_id, match.group(2), returned_raw)
                raise OumanProtocolError("No EH-800 property acknowledgement")
            except BaseException:
                await self._close_unlocked()
                raise
