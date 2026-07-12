"""Verify QNX Sensor Framework frames reach Python before a live shot."""

from __future__ import annotations

from pathlib import Path
import sys
from time import monotonic

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import QNX_PREFLIGHT_FRAME_COUNT
from platform_qnx.camera_qnx import QNXCamera, SensorFrameworkSource


def main() -> None:
    """Read a bounded sample of BGR frames and report observed delivery rate."""
    camera = QNXCamera(SensorFrameworkSource())
    try:
        started_at = monotonic()
        frame = None
        for _ in range(QNX_PREFLIGHT_FRAME_COUNT):
            frame = camera.read_frame()
        elapsed = monotonic() - started_at
        assert frame is not None
        observed_fps = QNX_PREFLIGHT_FRAME_COUNT / elapsed if elapsed else 0.0
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise RuntimeError(f"Expected BGR frame, received shape {frame.shape}.")
        print(
            "QNX preflight passed: "
            f"BGR {camera.resolution[0]}x{camera.resolution[1]}, "
            f"reported {camera.fps:.1f} fps, observed {observed_fps:.1f} fps"
        )
    finally:
        camera.close()


if __name__ == "__main__":
    main()
