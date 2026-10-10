"""No-hardware tests for opt-in researcher console."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

FILE = Path(__file__).resolve().parents[1] / "tools" / "developer_console.py"
spec = importlib.util.spec_from_file_location("developer_console", FILE)
console = importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)


class LabTest(unittest.TestCase):
    def test_encoding_signed_raw(self):
        self.assertEqual(console.encode_write(134, -20), b"SET PROPERTY 134 65516\n")

    def test_encoding_pid_never_automatically_writes(self):
        self.assertEqual(console.encode_write(56, 250), b"SET PROPERTY 56 250\n")

    def test_rejects_invalid_16bit(self):
        for prop, raw in ((-1, 1), (70000, 1), (67, -90000), (67, 999999)):
            with self.subTest(prop=prop, raw=raw):
                with self.assertRaises(ValueError):
                    console.encode_write(prop, raw)

    def test_verify_snapshot_min_count(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sample.txt"
            p.write_text("PROPERTY(67):'C'(0-1000) = 900\n")
            with self.assertRaises(ValueError):
                console.checked_snapshot(p)


if __name__ == "__main__":
    unittest.main()
