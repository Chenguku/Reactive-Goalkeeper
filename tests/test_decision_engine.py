from core.decision_engine import DecisionEngine
from core.trajectory import TrajectoryEstimate


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _estimate(speed: float, direction: str, sample_count: int = 2) -> TrajectoryEstimate:
    return TrajectoryEstimate(speed, 0.0, speed, 0.0, direction, sample_count)


def test_starts_timer_only_after_shot_speed_threshold() -> None:
    clock = FakeClock()
    engine = DecisionEngine(clock=clock, min_shot_speed_px_per_sec=100, default_delay_ms=50, reaction_budget_ms=200)

    assert engine.update(_estimate(99, "left")) is None
    assert not engine.shot_started
    assert engine.update(_estimate(100, "left")) is None
    assert engine.shot_started


def test_uses_latest_estimate_after_minimum_reaction_delay() -> None:
    clock = FakeClock()
    engine = DecisionEngine(clock=clock, min_shot_speed_px_per_sec=100, default_delay_ms=50, reaction_budget_ms=200)
    engine.update(_estimate(150, "left"))

    clock.now = 0.03
    assert engine.update(_estimate(180, "right", sample_count=3)) is None
    clock.now = 0.05
    decision = engine.poll()

    assert decision is not None
    assert decision.direction == "RIGHT"
    assert decision.latency_ms == 50
    assert decision.budget_used_ms == 50
    assert not decision.degraded


def test_poll_commits_by_deadline_without_waiting() -> None:
    clock = FakeClock()
    engine = DecisionEngine(clock=clock, min_shot_speed_px_per_sec=100, default_delay_ms=150, reaction_budget_ms=200)
    engine.update(_estimate(150, "center"))

    clock.now = 0.2
    decision = engine.poll()

    assert decision is not None
    assert decision.direction == "CENTER"
    assert decision.latency_ms == 200
    assert decision.degraded


def test_decision_is_committed_once() -> None:
    clock = FakeClock()
    engine = DecisionEngine(clock=clock, min_shot_speed_px_per_sec=100, default_delay_ms=0, reaction_budget_ms=200)

    first = engine.update(_estimate(150, "left"))
    second = engine.update(_estimate(150, "right"))

    assert first is not None
    assert second == first
    assert second.direction == "LEFT"
