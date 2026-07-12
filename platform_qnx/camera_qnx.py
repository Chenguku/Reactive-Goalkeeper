"""QNX Sensor Framework camera adapter for Raspberry Pi Camera Module 3.

QNX exposes CSI cameras through Sensor Framework's C Camera API, not V4L2.
The target-local frame source supplied here is responsible for consuming that
API's viewfinder callback or Screen stream and returning a copied frame.
"""

from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np

from core.camera_interface import Camera
from core.config import (
    QNX_CAMERA_FPS,
    QNX_CAMERA_PIXEL_FORMAT,
    QNX_CAMERA_RESOLUTION,
    QNX_CAMERA_UNIT,
    QNX_FALLBACK_CAMERA_FPS,
    QNX_FALLBACK_CAMERA_RESOLUTION,
)


@dataclass(frozen=True)
class QNXFrame:
    """One tightly packed frame supplied by the QNX Sensor Framework bridge."""

    pixels: np.ndarray
    pixel_format: str
    resolution: tuple[int, int]
    fps: float


class QNXSensorFrameSource(Protocol):
    """Target-local binding around QNX's C Camera API and Sensor service."""

    def open(
        self,
        *,
        unit: int,
        resolution: tuple[int, int],
        fps: float,
        pixel_format: str,
    ) -> None:
        """Open and configure a Sensor Framework camera unit."""

    def read(self) -> QNXFrame:
        """Return the next copied viewfinder frame from the Sensor service."""

    def close(self) -> None:
        """Stop viewfinder capture and close the camera handle."""


class SensorFrameworkSource:
    """CPython bridge backed directly by QNX Sensor Framework's Camera API."""

    def __init__(self) -> None:
        try:
            from platform_qnx import _sensor_camera
        except ImportError as error:
            raise RuntimeError(
                "The QNX Camera API extension is not built. On a QNX SDK host, run "
                "`python3 platform_qnx/setup_qnx_adapter.py build_ext --inplace`, then copy "
                "the resulting _sensor_camera module to the target image."
            ) from error
        self._native = _sensor_camera
        self._handle: object | None = None
        self._configured_fps = 0.0

    def open(
        self,
        *,
        unit: int,
        resolution: tuple[int, int],
        fps: float,
        pixel_format: str,
    ) -> None:
        if pixel_format.upper() != "NV12":
            raise ValueError("The native QNX bridge currently requests NV12 frames only.")
        # The Camera API checks the available mode after camera_set_vf_mode().
        # This first bridge uses the active Sensor Framework configuration; its
        # returned dimensions and measured FPS are verified by QNXCamera.
        self._handle = self._native.open_camera(unit)
        self._configured_fps = fps

    def read(self) -> QNXFrame:
        if self._handle is None:
            raise RuntimeError("QNX Sensor Framework source is not open.")
        pixels, width, height, measured_fps = self._native.read_nv12_frame(self._handle)
        return QNXFrame(
            pixels=np.frombuffer(pixels, dtype=np.uint8).reshape(height * 3 // 2, width),
            pixel_format="NV12",
            resolution=(width, height),
            fps=measured_fps if measured_fps > 0 else self._configured_fps,
        )

    def close(self) -> None:
        if self._handle is not None:
            self._native.close_camera(self._handle)
            self._handle = None


class QNXCamera(Camera):
    """BGR-frame camera backend over a QNX Sensor Framework frame source.

    The QNX C API has no supported Python binding. ``frame_source`` therefore
    bridges the C Camera API on the target and supplies NV12, RGB, BGR, or
    Bayer frames. It must negotiate the requested mode with the Sensor service
    and report the active mode in every ``QNXFrame``.
    """

    def __init__(
        self,
        frame_source: QNXSensorFrameSource,
        *,
        unit: int = QNX_CAMERA_UNIT,
        resolution: tuple[int, int] = QNX_CAMERA_RESOLUTION,
        fps: float = QNX_CAMERA_FPS,
        pixel_format: str = QNX_CAMERA_PIXEL_FORMAT,
        require_requested_mode: bool = False,
    ) -> None:
        self._source = frame_source
        self._unit = unit
        self._resolution = resolution
        self._fps = float(fps)
        self._pixel_format = pixel_format.upper()
        self._require_requested_mode = require_requested_mode
        self._active_resolution: tuple[int, int] | None = None
        self._active_fps: float | None = None
        self._source.open(
            unit=self._unit,
            resolution=self._resolution,
            fps=self._fps,
            pixel_format=self._pixel_format,
        )

    def read_frame(self) -> np.ndarray:
        """Return the next Sensor Framework frame as a BGR OpenCV array."""
        frame = self._source.read()
        self._validate_active_mode(frame)
        return self._to_bgr(frame)

    @property
    def fps(self) -> float:
        """Return the active rate once the Sensor Framework has delivered a frame."""
        return self._active_fps if self._active_fps is not None else self._fps

    @property
    def resolution(self) -> tuple[int, int]:
        """Return the active resolution once the Sensor Framework has delivered a frame."""
        return self._active_resolution if self._active_resolution is not None else self._resolution

    def close(self) -> None:
        """Release the Sensor Framework camera unit."""
        self._source.close()

    def _validate_active_mode(self, frame: QNXFrame) -> None:
        self._active_resolution = frame.resolution
        self._active_fps = frame.fps
        if not self._require_requested_mode or (
            frame.resolution == self._resolution and np.isclose(frame.fps, self._fps)
        ):
            return
        fallback = f"{QNX_FALLBACK_CAMERA_RESOLUTION} @ {QNX_FALLBACK_CAMERA_FPS} fps"
        raise RuntimeError(
            "QNX Sensor Framework negotiated "
            f"{frame.resolution} @ {frame.fps:g} fps, not the configured "
            f"{self._resolution} @ {self._fps:g} fps. Measure end-to-end throughput; "
            f"if the target cannot sustain the requested mode, change core/config.py "
            f"to the documented fallback {fallback}."
        )

    @staticmethod
    def _to_bgr(frame: QNXFrame) -> np.ndarray:
        width, height = frame.resolution
        pixel_format = frame.pixel_format.upper()
        pixels = frame.pixels

        if pixel_format == "BGR":
            QNXCamera._require_shape(pixels, (height, width, 3), pixel_format)
            return pixels
        if pixel_format == "RGB":
            QNXCamera._require_shape(pixels, (height, width, 3), pixel_format)
            return cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR)
        if pixel_format == "NV12":
            QNXCamera._require_shape(pixels, (height * 3 // 2, width), pixel_format)
            return cv2.cvtColor(pixels, cv2.COLOR_YUV2BGR_NV12)

        bayer_conversions = {
            "BAYER_RGGB8": cv2.COLOR_BAYER_RG2BGR,
            "BAYER_BGGR8": cv2.COLOR_BAYER_BG2BGR,
            "BAYER_GBRG8": cv2.COLOR_BAYER_GB2BGR,
            "BAYER_GRBG8": cv2.COLOR_BAYER_GR2BGR,
        }
        if pixel_format in bayer_conversions:
            QNXCamera._require_shape(pixels, (height, width), pixel_format)
            return cv2.cvtColor(pixels, bayer_conversions[pixel_format])
        raise ValueError(f"Unsupported QNX Sensor Framework pixel format: {frame.pixel_format}")

    @staticmethod
    def _require_shape(pixels: np.ndarray, expected: tuple[int, ...], pixel_format: str) -> None:
        if pixels.shape != expected:
            raise ValueError(
                f"{pixel_format} frame shape {pixels.shape} does not match expected {expected}. "
                "The QNX frame source must remove row padding before returning a frame."
            )
