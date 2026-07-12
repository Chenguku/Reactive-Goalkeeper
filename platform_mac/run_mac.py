"""Run one end-to-end Reflex Keeper shot using the macOS camera."""

from __future__ import annotations

from collections import deque
from pathlib import Path
import sys
from time import monotonic
from typing import Callable

# Allow the documented `python platform_mac/run_mac.py` invocation from the
# repository root without requiring an editable package installation.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.ball_detector import BallDetector
from core.config import REACTION_BUDGET_MS, TRACK_HISTORY_LENGTH
from core.decision_engine import Decision, DecisionEngine
from core.decision_output import DecisionEmitter
from core.trajectory import PositionSample, TrajectoryEstimator
from platform_mac.camera_mac import MacCamera


def run_pipeline(
    camera: MacCamera,
    detector: BallDetector,
    trajectory_estimator: TrajectoryEstimator,
    decision_engine: DecisionEngine,
    emitter: DecisionEmitter,
    *,
    clock: Callable[[], float] = monotonic,
) -> Decision:
    """Capture one shot, emit its decision, and return the committed result."""
    history: deque[PositionSample] = deque(maxlen=TRACK_HISTORY_LENGTH)
    previous_state = detector.tracking_state
    last_detection: PositionSample | None = None

    while True:
        frame = camera.read_frame()
        timestamp = clock()
        detection = detector.detect(frame)
        state = detector.tracking_state
        estimate = None

        if state == "tracking":
            if previous_state != "tracking":
                # Retain the most recent pre-launch point, so an estimate can
                # be made immediately from the first accepted moving point.
                history.clear()
                if last_detection is not None:
                    history.append(last_detection)
            if detection is not None:
                history.append((detection.position[0], detection.position[1], timestamp))
            estimate = trajectory_estimator.estimate(tuple(history))
        elif state == "searching":
            history.clear()

        if detection is not None:
            last_detection = (detection.position[0], detection.position[1], timestamp)

        decision = decision_engine.update(estimate) if estimate is not None else decision_engine.poll()
        if decision is not None:
            emitter.emit(
                decision.direction,
                latency_ms=decision.latency_ms,
                budget_ms=REACTION_BUDGET_MS,
                deadline_met=decision.latency_ms <= REACTION_BUDGET_MS,
            )
            return decision

        previous_state = state


def main() -> None:
    """Construct the macOS pipeline and print one JSON decision event."""
    camera = MacCamera()
    emitter = DecisionEmitter()
    try:
        run_pipeline(
            camera,
            BallDetector(),
            TrajectoryEstimator(frame_width=camera.resolution[0]),
            DecisionEngine(),
            emitter,
        )
    except KeyboardInterrupt:
        # A manual stop before a shot is normal during camera setup.
        pass
    finally:
        emitter.close()
        camera.close()


if __name__ == "__main__":
    main()
