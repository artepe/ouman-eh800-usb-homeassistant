"""Regression tests for the unchanged L1 control map and saved PID data."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components" / "ouman_eh800")
)
from usb_protocol.client import SAFE_WRITABLE_RAW_RANGES  # noqa: E402
from control_definitions import (  # noqa: E402
    PID_IDS,
    PID_PROPS,
    WRITABLE_PROPS,
    WRITABLE_RAW_RANGES,
    load_property_snapshot,
)


class ControlsTest(unittest.TestCase):
    def test_exactly_twelve_existing_controls_remain_writable(self):
        self.assertEqual(set(WRITABLE_RAW_RANGES), {
            54, 55, 67, 69, 71, 73, 75, 91, 92, 126, 127, 134,
        })
        self.assertEqual({p[0] for p in WRITABLE_PROPS} & PID_IDS, set())
        self.assertEqual(SAFE_WRITABLE_RAW_RANGES, WRITABLE_RAW_RANGES)

    def test_pid_read_only_metadata(self):
        self.assertEqual({p[0] for p in PID_PROPS}, {56, 57, 58})
        self.assertTrue(PID_IDS.isdisjoint(WRITABLE_RAW_RANGES))

    def test_snapshot_uses_unsigned_signed_conversion_and_never_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ouman_properties.txt"
            path.write_text(
                "PROPERTY(56):'L1_SAATIMEN_P_ALUE'(2-600) = 250\n"
                "PROPERTY(57):'L1_SAATIMEN_I_AIKA'(5-300) = 50\n"
                "PROPERTY(58):'L1_SAATIMEN_D_AIKA'(0-100) = 0\n"
                "PROPERTY(134):'L1_HIENOSAATO_VESI'(0-100) = 65516\n"
            )
            self.assertEqual(
                load_property_snapshot(path), {
                    56: 250, 57: 50, 58: 0, 134: -20
                }
            )

    def test_missing_snapshot_returns_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                load_property_snapshot(Path(directory) / "absent.txt"), {}
            )


if __name__ == "__main__":
    unittest.main()
