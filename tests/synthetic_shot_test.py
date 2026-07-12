"""Offline deadline validation using synthetic ball positions, not a camera."""

from dataclasses import dataclass

from core.config import REACTION_BUDGET_MS
from core.decision_engine import Decision, DecisionEngine
from core.trajectory import TrajectoryEstimator


FRAME_WIDTH = 1280
FRAME_INTERVAL_S = 1 / 50
SAMPLES_PER_SHOT = 10


class FakeClock:
    """Clock controlled by the synthetic sample timestamps."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@dataclass(frozen=True)
class SyntheticShot:
    """A constant-velocity pixel trajectory and its expected dive direction."""

    name: str
    start: tuple[float, float]
    pixels_per_frame: tuple[float, float]
    expected_direction: str


@dataclass(frozen=True)
class ShotResult:
    """Decision timing result for one synthetic trajectory."""

    name: str
    decision: Decision
    elapsed_from_shot_detection_ms: float

    @property
    def met_budget(self) -> bool:
        return self.elapsed_from_shot_detection_ms <= REACTION_BUDGET_MS


@dataclass(frozen=True)
class SyntheticShotReport:
    """Aggregate deadline result across the synthetic shot set."""

    results: tuple[ShotResult, ...]

    @property
    def total_shots(self) -> int:
        return len(self.results)

    @property
    def decisions_within_budget(self) -> int:
        return sum(result.met_budget for result in self.results)


SHOTS = (
    SyntheticShot("fast-left", (520, 360), (-14, 9), "LEFT"),
    SyntheticShot("steep-center", (640, 260), (1, 18), "CENTER"),
    SyntheticShot("fast-right", (760, 420), (20, -7), "RIGHT"),
)


def _positions(shot: SyntheticShot) -> tuple[tuple[float, float, float], ...]:
    """Generate timestamped positions directly, without camera or detector I/O."""
    return tuple(
        (
            shot.start[0] + frame * shot.pixels_per_frame[0],
            shot.start[1] + frame * shot.pixels_per_frame[1],
            frame * FRAME_INTERVAL_S,
        )
        for frame in range(SAMPLES_PER_SHOT)
    )


def _run_shot(shot: SyntheticShot) -> ShotResult:
    clock = FakeClock()
    estimator = TrajectoryEstimator(frame_width=FRAME_WIDTH)
    engine = DecisionEngine(clock=clock)
    history: list[tuple[float, float, float]] = []
    shot_detected_at: float | None = None
    decision: Decision | None = None

    for sample in _positions(shot):
        history.append(sample)
        clock.now = sample[2]
        decision = engine.update(estimator.estimate(history))
        if engine.shot_started and shot_detected_at is None:
            shot_detected_at = clock.now
        if decision is not None:
            break

    assert shot_detected_at is not None, f"{shot.name} never crossed the shot-speed threshold"
    if decision is None:
        # Simulate a frame with no fresh position: the engine must still commit
        # at the configured deadline instead of waiting for another detection.
        clock.now = shot_detected_at + REACTION_BUDGET_MS / 1000.0
        decision = engine.poll()

    assert decision is not None
    return ShotResult(
        name=shot.name,
        decision=decision,
        elapsed_from_shot_detection_ms=(clock.now - shot_detected_at) * 1000.0,
    )


def run_synthetic_shots() -> SyntheticShotReport:
    """Run every trajectory and report decision deadline compliance."""
    return SyntheticShotReport(tuple(_run_shot(shot) for shot in SHOTS))


def test_synthetic_shots_produce_expected_decisions_within_budget() -> None:
    report = run_synthetic_shots()

    assert report.total_shots == len(SHOTS)
    assert report.decisions_within_budget == report.total_shots
    assert [result.decision.direction for result in report.results] == [
        shot.expected_direction for shot in SHOTS
    ]
    assert all(result.decision.latency_ms <= REACTION_BUDGET_MS for result in report.results)


if __name__ == "__main__":
    report = run_synthetic_shots()
    for result in report.results:
        print(
            f"{result.name}: {result.decision.direction} "
            f"in {result.elapsed_from_shot_detection_ms:.1f} ms "
            f"(within budget: {result.met_budget})"
        )
    print(f"Deadline compliance: {report.decisions_within_budget}/{report.total_shots}")
