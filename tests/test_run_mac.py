from core.ball_detector import BallDetection
from core.decision_engine import DecisionEngine
from core.decision_output import DecisionEmitter
from core.trajectory import TrajectoryEstimator
from platform_mac.run_mac import run_pipeline


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 0.05
        return self.now


class FakeCamera:
    def __init__(self, frame_count: int) -> None:
        self._frames = iter(range(frame_count))

    def read_frame(self) -> int:
        return next(self._frames)


class FakeDetector:
    def __init__(self) -> None:
        self.tracking_state = "resting"

    def detect(self, _: int) -> BallDetection | None:
        positions = ((400, 400), (410, 400), (450, 400), (500, 400), (550, 400))
        index = _
        if index >= len(positions):
            return None
        if index >= 2:
            self.tracking_state = "tracking"
        position = positions[index]
        return BallDetection(position, radius=12, confidence=0.9)


class RecordingEmitter(DecisionEmitter):
    def __init__(self) -> None:
        self.events = []

    def emit(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        self.events.append((args, kwargs))


def test_mac_loop_wires_detection_to_one_console_event() -> None:
    clock = FakeClock()
    emitter = RecordingEmitter()
    decision = run_pipeline(
        FakeCamera(frame_count=5),  # type: ignore[arg-type]
        FakeDetector(),  # type: ignore[arg-type]
        TrajectoryEstimator(frame_width=1280),
        DecisionEngine(
            clock=clock,
            min_shot_speed_px_per_sec=100,
            default_delay_ms=100,
            reaction_budget_ms=800,
        ),
        emitter,
        clock=clock,
    )

    assert decision.direction == "LEFT"
    assert len(emitter.events) == 1
    _, fields = emitter.events[0]
    assert fields["budget_ms"] == 800
    assert fields["deadline_met"] is True
