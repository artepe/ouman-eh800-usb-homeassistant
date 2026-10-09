"""Hardware-free protocol tests with a fake serialx stream."""

import asyncio

import pytest

from ouman_eh800_usb_protocol import (
    OumanUSBClient,
    ProtocolError,
    parse_measurement_line,
    parse_property_line,
)


class FakeWriter:
    def __init__(self, reader, responder):
        self.reader = reader
        self.responder = responder
        self.commands = []
        self.closed = False

    def write(self, payload):
        self.commands.append(payload)
        reply = self.responder(payload)
        # Simulate 256-byte network proxy forwarding, including line splits.
        if reply is not None:
            for index in range(0, len(reply), 256):
                self.reader.feed_data(reply[index : index + 256])

    async def drain(self):
        await asyncio.sleep(0)

    def close(self):
        self.closed = True

    async def wait_closed(self):
        await asyncio.sleep(0)


def measurement_response():
    return (b"MEASUREMENTS\r\n" +
            b"".join(f"Sensor {i}: {i}.5 C\r\n".encode("ascii")
                     for i in range(1, 29)))


def install_fake(monkeypatch, responder):
    import ouman_eh800_usb_protocol.client as module

    instances = []

    async def open_serial_connection(**kwargs):
        assert kwargs["url"] == "socket://127.0.0.1:4001"
        assert kwargs["baudrate"] == 9600
        reader = asyncio.StreamReader()
        writer = FakeWriter(reader, responder)
        instances.append(writer)
        return reader, writer

    monkeypatch.setattr(module.serialx, "open_serial_connection", open_serial_connection)
    return instances


def test_parsers():
    assert parse_measurement_line("9: -7.5 C").value == -7.5
    assert parse_measurement_line("27  1 dig").unit == "dig"
    assert parse_measurement_line("MEASUREMENTS") is None
    reply = parse_property_line("PROPERTY(67):'L1_KAYRAN_MENOVESI_5A'(0-1000) = 910")
    assert reply.property_id == 67
    assert reply.maximum == 1000
    assert reply.raw_value == 910
    assert parse_property_line("SET PROPERTY 67 910") is None


def test_persistent_connection_and_proxy_chunks(monkeypatch):
    writers = install_fake(monkeypatch, lambda command: measurement_response())

    async def scenario():
        async with OumanUSBClient("socket://127.0.0.1:4001") as client:
            first = await client.measurements()
            second = await client.measurements()
            assert len(first) == 28
            assert first[0].value == 1.5
            assert second[27].value == 28.5
            assert len(writers) == 1
            assert writers[0].commands == [b"MEASUREMENTS\n", b"MEASUREMENTS\n"]
        assert writers[0].closed

    asyncio.run(scenario())


def test_write_reply_and_signed_value(monkeypatch):
    writers = install_fake(
        monkeypatch,
        lambda command: b"SET PROPERTY 134 65526\r\n" +
        b"PROPERTY(134):'L1_HIENOSAATO_VESI'(-40-40) = 65526\r\n",
    )

    async def scenario():
        async with OumanUSBClient("socket://127.0.0.1:4001") as client:
            reply = await client.write_property(134, 65526)
            assert reply.raw_value == 65526
            assert reply.signed_value == -10
            assert reply.minimum == -40
            assert reply.maximum == 40
            assert writers[0].commands == [b"SET PROPERTY 134 65526\n"]

    asyncio.run(scenario())


def test_wrong_property_response_does_not_retry_write(monkeypatch):
    writers = install_fake(
        monkeypatch,
        lambda command: b"PROPERTY(66):'OTHER'(0-1000) = 910\n",
    )

    async def scenario():
        client = OumanUSBClient("socket://127.0.0.1:4001")
        with pytest.raises(ProtocolError, match="Expected property"):
            await client.write_property(67, 910)
        assert writers[0].commands == [b"SET PROPERTY 67 910\n"]
        assert writers[0].closed

    asyncio.run(scenario())


def test_timeout_never_resends_write(monkeypatch):
    writers = install_fake(monkeypatch, lambda command: None)

    async def scenario():
        client = OumanUSBClient("socket://127.0.0.1:4001", timeout=0.025)
        with pytest.raises(ProtocolError, match="write may have succeeded"):
            await client.write_property(67, 910)
        assert len(writers[0].commands) == 1

    asyncio.run(scenario())


def test_disconnected_port_reconnects_on_next_poll(monkeypatch):
    calls = 0

    def responder(command):
        nonlocal calls
        calls += 1
        return b"" if calls == 1 else measurement_response()

    writers = install_fake(monkeypatch, responder)

    async def scenario():
        client = OumanUSBClient("socket://127.0.0.1:4001", timeout=0.025)
        with pytest.raises(ProtocolError):
            await client.measurements()
        result = await client.measurements()
        assert len(result) == 28
        assert len(writers) == 2
        await client.close()

    asyncio.run(scenario())
