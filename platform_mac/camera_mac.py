"""macOS webcam backend and manual preview utility."""

from pathlib import Path
import sys

# Support `python3 platform_mac/camera_mac.py` from the repo root.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

from core.camera_interface import Camera
from core.config import MAC_CAMERA_FPS, MAC_CAMERA_RESOLUTION


class MacCamera(Camera):
    """Camera backend for the built-in MacBook webcam."""

    def __init__(self) -> None:
        self._capture = cv2.VideoCapture(0)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, MAC_CAMERA_RESOLUTION[0])
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, MAC_CAMERA_RESOLUTION[1])
        self._capture.set(cv2.CAP_PROP_FPS, MAC_CAMERA_FPS)

        if not self._capture.isOpened():
            self._capture.release()
            raise RuntimeError("Unable to open the MacBook webcam.")

    def read_frame(self) -> np.ndarray:
        """Return the next frame from the webcam."""
        success, frame = self._capture.read()
        if not success:
            raise RuntimeError("Unable to read a frame from the MacBook webcam.")
        return frame

    @property
    def fps(self) -> float:
        """Return the configured capture frame rate."""
        return float(MAC_CAMERA_FPS)

    @property
    def resolution(self) -> tuple[int, int]:
        """Return the configured capture resolution as (width, height)."""
        return MAC_CAMERA_RESOLUTION

    def close(self) -> None:
        """Release the webcam device."""
        self._capture.release()


def main() -> None:
    """Show a live webcam preview; press q or Escape to exit."""
    camera = MacCamera()
    try:
        while True:
            cv2.imshow("Reflex Keeper — Mac Camera Preview", camera.read_frame())
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
    finally:
        camera.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
