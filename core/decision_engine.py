"""Deadline-aware, platform-independent goalkeeper dive decisions."""

from dataclasses import dataclass
from time import monotonic
from typing import Callable

from core.config import (
    MIN_SHOT_SPEED_PX_PER_SEC,
    REACTION_BUDGET_MS,
    REACTION_DEFAULT_DELAY_MS,
)
from core.trajectory import TrajectoryEstimate


@dataclass(frozen=True)
class Decision:
    """A committed goalkeeper action and the time spent deciding."""

    direction: str
    latency_ms: float
    estimate: TrajectoryEstimate | None
    degraded: bool

    @property
    def budget_used_ms(self) -> float:
        """Return the portion of the reaction budget used before commitment."""
        return self.latency_ms


class DecisionEngine:
    """Turn incoming trajectory estimates into exactly one deadline-bound decision.

    Call :meth:`update` whenever an estimate arrives and :meth:`poll` on frames
    with no estimate. Neither method sleeps or waits; they only inspect the
    injected clock, so a caller can never be blocked past the deadline.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        min_shot_speed_px_per_sec: float = MIN_SHOT_SPEED_PX_PER_SEC,
        default_delay_ms: float = REACTION_DEFAULT_DELAY_MS,
        reaction_budget_ms: float = REACTION_BUDGET_MS,
    ) -> None:
        if min_shot_speed_px_per_sec < 0:
            raise ValueError("min_shot_speed_px_per_sec cannot be negative.")
        if default_delay_ms < 0 or reaction_budget_ms <= 0:
            raise ValueError("Reaction delays must be non-negative and budget must be positive.")
        if default_delay_ms > reaction_budget_ms:
            raise ValueError("default_delay_ms cannot exceed reaction_budget_ms.")
        self._clock = clock
        self._min_shot_speed_px_per_sec = min_shot_speed_px_per_sec
        self._default_delay_ms = default_delay_ms
        self._reaction_budget_ms = reaction_budget_ms
        self.reset()

    @property
    def shot_started(self) -> bool:
        """Whether an estimate has crossed the configured shot-speed threshold."""
        return self._shot_started_at is not None

    @property
    def decision(self) -> Decision | None:
        """Return the committed decision, if the engine has made one."""
        return self._decision

    def reset(self) -> None:
        """Prepare the engine for one new shot."""
        self._shot_started_at: float | None = None
        self._best_estimate: TrajectoryEstimate | None = None
        self._decision: Decision | None = None

    def update(self, estimate: TrajectoryEstimate | None) -> Decision | None:
        """Accept a new estimate and return a decision when one is due."""
        if self._decision is not None:
            return self._decision

        now = self._clock()
        if self._shot_started_at is None:
            if estimate is None or estimate.speed_px_per_sec < self._min_shot_speed_px_per_sec:
                return None
            self._shot_started_at = now

        if estimate is not None:
            self._best_estimate = estimate
        return self._decide_if_due(now)

    def poll(self) -> Decision | None:
        """Return a due decision when no new trajectory estimate is available."""
        if self._decision is not None:
            return self._decision
        if self._shot_started_at is None:
            return None
        return self._decide_if_due(self._clock())

    def _decide_if_due(self, now: float) -> Decision | None:
        assert self._shot_started_at is not None
        elapsed_ms = max(0.0, (now - self._shot_started_at) * 1000.0)
        if elapsed_ms < self._default_delay_ms and elapsed_ms < self._reaction_budget_ms:
            return None

        estimate = self._best_estimate
        direction = self._direction_from_estimate(estimate)
        self._decision = Decision(
            direction=direction,
            latency_ms=min(elapsed_ms, self._reaction_budget_ms),
            estimate=estimate,
            degraded=estimate is None or elapsed_ms >= self._reaction_budget_ms,
        )
        return self._decision

    @staticmethod
    def _direction_from_estimate(estimate: TrajectoryEstimate | None) -> str:
        if estimate is None:
            return "CENTER"
        direction = estimate.direction.upper()
        return direction if direction in {"LEFT", "CENTER", "RIGHT"} else "CENTER"
