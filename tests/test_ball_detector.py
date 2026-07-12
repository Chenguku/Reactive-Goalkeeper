import cv2
import numpy as np

from core.ball_detector import BallDetector


FRAME_SIZE = (720, 1280, 3)
HSV_RANGE = ((10, 100, 100), (35, 255, 255))
ROI = (450, 300, 200, 200)


def _frame(*centers: tuple[int, int]) -> np.ndarray:
    frame = np.zeros(FRAME_SIZE, dtype=np.uint8)
    color = cv2.cvtColor(np.uint8([[[20, 255, 255]]]), cv2.COLOR_HSV2BGR)[0, 0].tolist()
    for center in centers:
        cv2.circle(frame, center, 12, color, -1)
    return frame


def _detector() -> BallDetector:
    return BallDetector(
        hsv_range=HSV_RANGE,
        initial_roi=ROI,
        min_radius_px=5,
        max_radius_px=20,
        min_circularity=0.6,
        min_speed_px_per_frame=10,
        initial_launch_max_displacement_px=250,
        prediction_gate_px=40,
        max_missed_frames=2,
    )


def test_initial_lock_ignores_matching_blob_outside_roi() -> None:
    detector = _detector()
    detection = detector.detect(_frame((530, 390), (900, 390)))

    assert detection is not None
    assert np.allclose(detection.position, (530, 390), atol=1)


def test_resting_ball_stays_locked_and_reported_before_launch() -> None:
    detector = _detector()

    first_detection = detector.detect(_frame((530, 390)))
    second_detection = detector.detect(_frame((530, 390)))

    assert first_detection is not None
    assert second_detection is not None
    assert detector.tracking_state == "resting"
    assert detector.resting_position is not None
    assert np.allclose(detector.resting_position, (530, 390), atol=1)


def test_resting_ball_can_lock_on_red_panel() -> None:
    frame = np.zeros(FRAME_SIZE, dtype=np.uint8)
    red = cv2.cvtColor(np.uint8([[[175, 255, 255]]]), cv2.COLOR_HSV2BGR)[0, 0].tolist()
    cv2.circle(frame, (530, 390), 12, red, -1)
    detector = BallDetector(
        initial_roi=ROI,
        min_radius_px=5,
        max_radius_px=20,
        min_circularity=0.6,
    )

    detection = detector.detect(frame)

    assert detection is not None
    assert detector.tracking_state == "resting"
    assert np.allclose(detection.position, (530, 390), atol=1)


def test_tracker_rejects_trajectory_inconsistent_candidate() -> None:
    detector = _detector()
    detector.detect(_frame((530, 390)))
    detector.detect(_frame((550, 390)))
    detection = detector.detect(_frame((570, 390), (900, 390)))

    assert detection is not None
    assert np.allclose(detection.position, (570, 390), atol=1)


def test_resting_lock_ignores_one_frame_distant_false_positive() -> None:
    detector = _detector()
    detector.detect(_frame((530, 390)))

    assert detector.detect(_frame((760, 390))) is None
    detection = detector.detect(_frame((530, 390)))

    assert detection is not None
    assert detector.tracking_state == "resting"
    assert np.allclose(detection.position, (530, 390), atol=1)


def test_resting_lock_starts_tracking_after_consistent_launch_motion() -> None:
    detector = _detector()
    detector.detect(_frame((530, 390)))

    assert detector.detect(_frame((600, 390))) is None
    detection = detector.detect(_frame((670, 390)))

    assert detection is not None
    assert detector.tracking_state == "tracking"
    assert np.allclose(detection.position, (670, 390), atol=1)


def test_tracker_survives_brief_missed_detection() -> None:
    detector = _detector()
    detector.detect(_frame((530, 390)))
    detector.detect(_frame((550, 390)))
    assert detector.detect(_frame()) is None
    detection = detector.detect(_frame((590, 390)))

    assert detection is not None
    assert np.allclose(detection.position, (590, 390), atol=1)
