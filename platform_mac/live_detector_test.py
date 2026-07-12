"""Manual live validation for the layered ball detector on a Mac webcam."""

from pathlib import Path
import sys

# Support `python3 platform_mac/live_detector_test.py` from the repo root.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

from core.ball_detector import BallDetection, BallDetector
from core.config import INITIAL_BALL_ROI
from platform_mac.camera_mac import MacCamera


WINDOW_TITLE = "Reflex Keeper — Ball Detector Test"


def _point(position: tuple[float, float]) -> tuple[int, int]:
    return (round(position[0]), round(position[1]))


def _draw_overlay(
    frame: np.ndarray,
    detector: BallDetector,
    detection: BallDetection | None,
    follow_through_test: bool,
) -> None:
    x, y, width, height = INITIAL_BALL_ROI
    cv2.rectangle(frame, (x, y), (x + width, y + height), (255, 180, 0), 2)
    cv2.putText(frame, "initial ball ROI", (x, max(24, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 180, 0), 2)

    trajectory = detector.trajectory
    for start, end in zip(trajectory, trajectory[1:]):
        cv2.line(frame, _point(start), _point(end), (0, 255, 255), 2)

    prediction = detector.predicted_position
    if prediction is not None:
        cv2.circle(frame, _point(prediction), round(detector.prediction_gate_px), (0, 255, 0), 2)
        cv2.circle(frame, _point(prediction), 3, (0, 255, 0), -1)
        cv2.putText(frame, "Kalman gate", _point(prediction), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    if detection is not None:
        center = _point(detection.position)
        is_resting = detector.tracking_state == "resting"
        color = (255, 180, 0) if is_resting else (0, 0, 255)
        label = "resting ball" if is_resting else "tracked ball"
        cv2.circle(frame, center, round(detection.radius), color, 2)
        cv2.circle(frame, center, 4, color, -1)
        cv2.putText(
            frame,
            f"{label} ({center[0]}, {center[1]}) confidence={detection.confidence:.2f}",
            (16, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
        )
    else:
        cv2.putText(
            frame,
            "place resting ball inside initial ball ROI",
            (16, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 0, 255),
            2,
        )

    state = detector.tracking_state.upper()
    status = "FOLLOW-THROUGH TEST ACTIVE" if follow_through_test else f"state: {state}"
    cv2.putText(frame, status, (16, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
    cv2.putText(frame, "r: reset  f: follow-through test  q/esc: quit", (16, frame.shape[0] - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)


def main() -> None:
    """Run a visual validation, including a real kicker follow-through."""
    camera = MacCamera()
    detector = BallDetector()
    follow_through_test = False
    try:
        while True:
            frame = camera.read_frame()
            detection = detector.detect(frame)
            _draw_overlay(frame, detector, detection, follow_through_test)
            cv2.imshow(WINDOW_TITLE, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("r"):
                detector.reset()
            if key == ord("f"):
                follow_through_test = not follow_through_test
                detector.reset()
    finally:
        camera.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
