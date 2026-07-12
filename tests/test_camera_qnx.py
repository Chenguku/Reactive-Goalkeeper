import cv2
import numpy as np

from platform_qnx.camera_qnx import QNXCamera, QNXFrame


class FakeSensorSource:
    def __init__(self, frame: QNXFrame) -> None:
        self.frame = frame
        self.open_arguments: dict[str, object] | None = None
        self.closed = False

    def open(self, **kwargs: object) -> None:
        self.open_arguments = kwargs

    def read(self) -> QNXFrame:
        return self.frame

    def close(self) -> None:
        self.closed = True


def test_qnx_camera_converts_nv12_sensor_frame_to_bgr() -> None:
    width, height = 4, 2
    bgr = np.full((height, width, 3), (20, 120, 220), dtype=np.uint8)
    i420 = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV_I420)
    y_plane = i420[:height]
    chroma = i420[height:].reshape(-1)
    chroma_size = width * height // 4
    u_plane = chroma[:chroma_size].reshape(height // 2, width // 2)
    v_plane = chroma[chroma_size:].reshape(height // 2, width // 2)
    uv_plane = np.empty((height // 2, width), dtype=np.uint8)
    uv_plane[:, 0::2] = u_plane
    uv_plane[:, 1::2] = v_plane
    nv12 = np.vstack((y_plane, uv_plane))
    source = FakeSensorSource(QNXFrame(nv12, "NV12", (width, height), 120))
    camera = QNXCamera(source, resolution=(width, height), fps=120)

    converted = camera.read_frame()

    assert converted.shape == bgr.shape
    assert np.allclose(converted, bgr, atol=3)
    assert source.open_arguments is not None


def test_qnx_camera_rejects_a_negotiated_mode_mismatch() -> None:
    source = FakeSensorSource(QNXFrame(np.zeros((3, 2), dtype=np.uint8), "NV12", (2, 2), 56))
    camera = QNXCamera(source, resolution=(2, 2), fps=120, require_requested_mode=True)

    try:
        camera.read_frame()
    except RuntimeError as error:
        assert "documented fallback" in str(error)
    else:
        raise AssertionError("QNXCamera accepted a mode mismatch")
