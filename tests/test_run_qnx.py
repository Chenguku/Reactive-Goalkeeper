from io import StringIO
from itertools import count

import numpy as np

from core.ball_detector import BallDetection
from core.decision_output import DecisionEmitter
from core.trajectory import TrajectoryEstimator
from platform_qnx.run_qnx import run_pipeline


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 0.05
        return self.now


class FakeCamera:
    def __init__(self) -> None:
        self._frames = count()

    def read_frame(self) -> np.ndarray:
        return np.array(next(self._frames))


class FakeDetector:
    def __init__(self) -> None:
        self.tracking_state = "resting"

    def detect(self, frame: np.ndarray) -> BallDetection | None:
        positions = ((400, 400), (410, 400), (450, 400), (500, 400), (550, 400))
        index = int(frame)
        if index >= len(positions):
            return None
        if index >= 2:
            self.tracking_state = "tracking"
        return BallDetection(positions[index], radius=12, confidence=0.9)


def test_qnx_pipeline_prioritizes_decision_and_emits_measured_latency() -> None:
    priorities: list[tuple[int, int]] = []
    clock = FakeClock()
    stream = StringIO()

    decision = run_pipeline(
        FakeCamera(),  # type: ignore[arg-type]
        FakeDetector(),  # type: ignore[arg-type]
        TrajectoryEstimator(frame_width=1280),
        DecisionEmitter(stream=stream),
        clock=clock,
        apply_scheduler=lambda policy, priority: priorities.append((policy, priority)),
    )

    assert decision.direction == "LEFT"
    assert len(priorities) == 2
    assert '"latency_ms"' in stream.getvalue()
