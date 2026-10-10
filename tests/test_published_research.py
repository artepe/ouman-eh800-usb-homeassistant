"""Static/non-device tests for the public USB research and recovery entry points."""
import ast
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def import_script(relative):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResearchTests(unittest.TestCase):
    def test_raw_capture_is_read_only(self):
        capture = import_script("tools/capture_raw_usb.py")
        self.assertIn("MEASUREMENTS", capture.COMMANDS)
        self.assertIn("TYPE objects.dat", capture.COMMANDS)
        self.assertNotIn("FIRMWARE", capture.COMMANDS)
        self.assertFalse(any("SET PROPERTY" in s for s in capture.COMMANDS))
        tx = b"MEASUREMENTS\n"
        data = capture.format_record("MEASUREMENTS", tx, b"abc\x00", ["61 62 63 00"])
        self.assertEqual(data["tx_hex"], tx.hex(" "))
        self.assertEqual(data["rx_hex"], "61 62 63 00")
        self.assertEqual(data["rx_length"], 4)

    def test_objects_inspector_is_offline_and_read_only(self):
        inspect = import_script("tools/inspect_objects.py")
        obj = bytearray(inspect.SIZE)
        obj[2536:2538] = (910).to_bytes(2, "little")
        obj[2546:2548] = (-200).to_bytes(2, "little", signed=True)
        rows, fine = inspect.inspect_data(bytes(obj))
        self.assertEqual(rows[0][0:4], (-20, 2536, 91.0, -20.0))
        self.assertEqual(fine, 0)
        with self.assertRaises(ValueError):
            inspect.inspect_data(b"x")

    def test_restore_is_manually_registered(self):
        path = ROOT / "custom_components/ouman_eh800/restore.py"
        source = path.read_text()
        parsed = ast.parse(source)
        self.assertIn("async_setup_restore", [
            n.name for n in parsed.body if isinstance(n, ast.AsyncFunctionDef)
        ])
        self.assertIn('"restore_original"', source)
        self.assertIn("len(props) < 250", source)

    def test_legacy_polling_retained(self):
        text = (ROOT / "custom_components/ouman_eh800/sensor.py").read_text()
        self.assertIn("SCAN_INTERVAL = timedelta(seconds=1)", text)


if __name__ == "__main__":
    unittest.main()
