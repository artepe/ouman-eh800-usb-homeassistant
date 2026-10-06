from __future__ import annotations
import re
import threading
import time
import serial

PROP_RE = re.compile(r"PROPERTY\((\d+)\):'([^']+)'\((\d+)-(\d+)\)\s*=\s*(\d+)")

class OumanUSB:
    def __init__(self, port: str):
        self.port = port
        self.lock = threading.Lock()

    def _command(self, command: str, wait: float = 0.18) -> str:
        with self.lock:
            with serial.Serial(self.port, timeout=0.35) as s:
                time.sleep(0.08)
                s.reset_input_buffer()
                s.write((command + "\n").encode("ascii"))
                s.flush()
                time.sleep(wait)
                out = bytearray()
                while True:
                    chunk = s.read(4096)
                    if not chunk:
                        break
                    out.extend(chunk)
                return bytes(out).decode("latin1", errors="replace")

    def measurements(self) -> list[tuple[float, str]]:
        text = self._command("MEASUREMENTS", 0.30)
        result = []
        for line in text.replace("\r", "").split("\n"):
            m = re.search(r"(-?\d+(?:\.\d+)?)\s*(C|%|dig)\s*$", line.strip(), re.I)
            if m:
                result.append((float(m.group(1)), m.group(2)))
        return result

    def property(self, prop_id: int, value: int) -> tuple[int, str, int, int, int]:
        text = self._command(f"SET PROPERTY {prop_id} {value}")
        m = PROP_RE.search(text)
        if not m:
            raise RuntimeError(f"Unexpected EH-800 response: {text!r}")
        return int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(4)), int(m.group(5))
