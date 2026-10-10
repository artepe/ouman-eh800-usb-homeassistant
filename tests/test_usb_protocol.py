"""Hardware-free regression tests for the serial protocol.

Run: python -m unittest discover -s tests -v
"""
import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "ouman_eh800"))

from usb_protocol import AsyncOumanUSB, OumanProtocolError  # noqa: E402


class FakeWriter:
    def __init__(self, reader, chunks):
        self.reader = reader
        self.chunks = chunks
        self.sent = []
        self.closed = False

    def write(self, data):
        self.sent.append(data)

    async def drain(self):
        for chunk in self.chunks:
            self.reader.feed_data(chunk)
        self.chunks = []

    def close(self):
        self.closed = True
        self.reader.feed_eof()

    async def wait_closed(self):
        pass


def transport(chunks):
    reader = asyncio.StreamReader()
    writer = FakeWriter(reader, chunks)

    async def connect(*, url):
        assert url == "socket://127.0.0.1:4001"
        return reader, writer

    return connect, writer


class AsyncProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_fragmented_complete_28_measurements(self):
        frame = "".join(f"Measurement {i}: {i}.5 C\r\n" for i in range(28))
        chunks = [frame.encode()[j:j + 3] for j in range(0, len(frame.encode()), 3)]
        factory, writer = transport(chunks)
        client = AsyncOumanUSB("socket://127.0.0.1:4001", connection_factory=factory)
        values = await client.measurements()
        self.assertEqual(len(values), 28)
        self.assertEqual(values[9], (9.5, "C"))
        self.assertEqual(writer.sent, [b"MEASUREMENTS\n"])
        await client.disconnect()
        self.assertTrue(writer.closed)

    async def test_refuses_truncated_measurements(self):
        frame = "".join(f"Measurement {i}: {i} %\n" for i in range(27))
        factory, writer = transport([frame.encode()])
        client = AsyncOumanUSB(
            "socket://127.0.0.1:4001", timeout=0.04, connection_factory=factory
        )
        with self.assertRaises(OumanProtocolError):
            await client.measurements()
        self.assertTrue(writer.closed)

    async def test_disallow_pid_and_out_of_range_writes(self):
        factory, writer = transport([])
        client = AsyncOumanUSB("socket://127.0.0.1:4001", connection_factory=factory)
        with self.assertRaises(ValueError):
            await client.set_property(56, 250)
        with self.assertRaises(ValueError):
            await client.set_property(67, 4000)
        for pid in (56, 57, 58):
            with self.assertRaises(ValueError):
                await client.set_property(pid, 20)
        self.assertEqual(writer.sent, [])

    async def test_safe_property_write_requires_matching_ack(self):
        factory, writer = transport(
            [b"SET PROPERTY 67 910\r\nPROPERTY(67):'L1_KAYRAN_MENOVESI_5A'(0-1000) = 910\r\n"]
        )
        client = AsyncOumanUSB("socket://127.0.0.1:4001", connection_factory=factory)
        reply = await client.set_property(67, 910)
        self.assertEqual(reply.property_id, 67)
        self.assertEqual(reply.raw_value, 910)
        self.assertEqual(writer.sent, [b"SET PROPERTY 67 910\n"])
        await client.disconnect()


    async def test_all_non_pid_properties_are_writable_with_matching_ack(self):
        allowed = {
            54: 140, 55: 890, 67: 900, 69: 700, 71: 550,
            73: 490, 75: 180, 91: 24, 92: 81, 126: 40,
            127: 150, 134: -20,
        }
        for pid, raw in allowed.items():
            with self.subTest(property=pid):
                wire = raw & 0xFFFF
                factory, writer = transport([
                    f"PROPERTY({pid}):'TEST'(0-1000) = {wire}\r\n".encode()
                ])
                client = AsyncOumanUSB(
                    "socket://127.0.0.1:4001", connection_factory=factory
                )
                response = await client.set_property(pid, raw)
                self.assertEqual(response.property_id, pid)
                self.assertEqual(response.raw_value, wire)
                self.assertEqual(writer.sent, [
                    f"SET PROPERTY {pid} {wire}\n".encode()
                ])
                await client.disconnect()

    async def test_mismatched_write_reply_is_not_accepted(self):
        factory, writer = transport([
            b"PROPERTY(69):'WRONG'(0-1000) = 910\r\n"
        ])
        client = AsyncOumanUSB(
            "socket://127.0.0.1:4001", connection_factory=factory
        )
        with self.assertRaises(OumanProtocolError):
            await client.set_property(67, 910)
        self.assertTrue(writer.closed)
        self.assertEqual(len(writer.sent), 1)


if __name__ == "__main__":
    unittest.main()
