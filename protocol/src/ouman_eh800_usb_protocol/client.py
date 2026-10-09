"""Async serialx transport for the reverse-engineered Ouman USB service shell.

This module intentionally has no Home Assistant imports. It does not change the
live integration in custom_components/ouman_eh800.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import re
from typing import Any

import serialx

_LOGGER = logging.getLogger(__name__)

_MEASUREMENT_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(C|%|dig)\s*$", re.I)
_PROPERTY_RE = re.compile(
    r"PROPERTY\(\s*(\d+)\s*\):'([^']+)'\(([^)]*)\)\s*=\s*(-?\d+)",
    re.I,
)
_RANGE_RE = re.compile(r"^\s*(-?\d+)\s*-\s*(-?\d+)\s*$")


class ProtocolError(Exception):
    """Response did not match the documented service-shell framing."""


@dataclass(frozen=True, slots=True)
class Measurement:
    value: float
    unit: str


@dataclass(frozen=True, slots=True)
class PropertyReply:
    property_id: int
    name: str
    minimum: int | None
    maximum: int | None
    raw_value: int

    @property
    def signed_value(self) -> int:
        """Interpret unsigned 16-bit values as signed when appropriate."""
        return self.raw_value - 65536 if 32768 <= self.raw_value <= 65535 else self.raw_value


def parse_measurement_line(line: str) -> Measurement | None:
    """Extract one measurement while ignoring command echoes and headings."""
    match = _MEASUREMENT_RE.search(line.strip())
    if match is None:
        return None
    return Measurement(float(match.group(1)), match.group(2))


def parse_property_line(line: str) -> PropertyReply | None:
    """Parse a SET PROPERTY response."""
    match = _PROPERTY_RE.search(line)
    if match is None:
        return None
    range_match = _RANGE_RE.fullmatch(match.group(3))
    return PropertyReply(
        property_id=int(match.group(1)),
        name=match.group(2),
        minimum=int(range_match.group(1)) if range_match else None,
        maximum=int(range_match.group(2)) if range_match else None,
        raw_value=int(match.group(4)),
    )


class OumanUSBClient:
    """One persistent serial connection with serialized request/response pairs.

    MEASUREMENTS completion is based on the 28 expected measurement records, not
    on arbitrary idle-read delays. Property responses have an explicit matching
    PROPERTY(id) line. Framing should still be verified with real hardware logs
    before enabling this as the default Home Assistant transport.
    """

    def __init__(
        self,
        port: str,
        *,
        baudrate: int = 9600,
        measurement_count: int = 28,
        timeout: float = 6.0,
    ) -> None:
        if not port:
            raise ValueError("port must be specified")
        if measurement_count < 1 or timeout <= 0:
            raise ValueError("measurement_count and timeout must be positive")
        self.port = port
        self.baudrate = baudrate
        self.measurement_count = measurement_count
        self.timeout = timeout
        self._reader: Any | None = None
        self._writer: Any | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Open transport once. Calls are safe to repeat."""
        async with self._lock:
            await self._connect_locked()

    async def _connect_locked(self) -> None:
        if self._writer is not None:
            return
        self._reader, self._writer = await serialx.open_serial_connection(
            url=self.port, baudrate=self.baudrate
        )

    async def close(self) -> None:
        async with self._lock:
            await self._close_locked()

    async def _close_locked(self) -> None:
        writer = self._writer
        self._writer = None
        self._reader = None
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, ConnectionError):
                pass

    async def _read_lines_locked(
        self, command: str, *, property_id: int | None = None
    ) -> list[str]:
        await self._connect_locked()
        assert self._reader is not None and self._writer is not None

        lines: list[str] = []
        measurements = 0
        bytes_seen = 0
        # The lock covers the entire exchange, so a poll cannot consume a
        # property-write reply or vice versa.
        try:
            self._writer.write((command + "\n").encode("ascii"))
            await self._writer.drain()
            async with asyncio.timeout(self.timeout):
                while len(lines) < 128 and bytes_seen < 65536:
                    raw = await self._reader.readline()
                    if not raw:
                        raise ProtocolError("Ouman serial connection closed mid-response")
                    bytes_seen += len(raw)
                    line = raw.decode("latin1", errors="replace").strip()
                    lines.append(line)

                    if property_id is not None:
                        reply = parse_property_line(line)
                        if reply is not None:
                            if reply.property_id != property_id:
                                raise ProtocolError(
                                    f"Expected property {property_id}, got {reply.property_id}"
                                )
                            return lines
                    elif parse_measurement_line(line) is not None:
                        measurements += 1
                        if measurements == self.measurement_count:
                            return lines
            raise ProtocolError("Ouman response exceeded safety limit")
        except BaseException:
            # Never automatically resend a SET PROPERTY command. It may have
            # succeeded before the response was lost.
            await self._close_locked()
            raise

    async def measurements(self) -> list[Measurement]:
        """Read one complete MEASUREMENTS frame."""
        async with self._lock:
            try:
                lines = await self._read_lines_locked("MEASUREMENTS")
            except TimeoutError as err:
                raise ProtocolError("Timed out waiting for MEASUREMENTS") from err
            values = [value for line in lines if (value := parse_measurement_line(line))]
            if len(values) != self.measurement_count:
                raise ProtocolError("Incomplete MEASUREMENTS frame")
            return values

    async def write_property(self, property_id: int, raw_value: int) -> PropertyReply:
        """Explicit write only. Caller must validate permitted IDs/ranges.

        Never invoke this to read a property. No PID or bulk-restore operations
        are exposed from this library automatically.
        """
        if not (0 <= property_id <= 65535 and 0 <= raw_value <= 65535):
            raise ValueError("Property ID and raw wire value must fit uint16")
        async with self._lock:
            try:
                lines = await self._read_lines_locked(
                    f"SET PROPERTY {property_id} {raw_value}", property_id=property_id
                )
            except TimeoutError as err:
                raise ProtocolError(
                    f"Timed out waiting for PROPERTY({property_id}); write may have succeeded"
                ) from err
            for line in lines:
                reply = parse_property_line(line)
                if reply is not None:
                    return reply
            raise ProtocolError("Missing property reply")

    async def __aenter__(self) -> OumanUSBClient:
        await self.connect()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()
