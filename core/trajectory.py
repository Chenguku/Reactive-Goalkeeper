"""Pure short-history ball trajectory estimation."""

from dataclasses import dataclass
from math import atan2, degrees, hypot
from typing import Sequence

from core.config import DIRECTION_CENTER_DEADZONE_PX


PositionSample = tuple[float, float, float]


@dataclass(frozen=True)
class TrajectoryEstimate:
    """Velocity and horizontal dive classification from recent ball positions.

    ``angle_degrees`` uses image coordinates: 0° points right, 90° points
    down, -90° points up. ``direction`` is based on the latest observed
    horizontal ball position relative to the frame centre.
    """

    speed_px_per_sec: float
    angle_degrees: float
    velocity_x_px_per_sec: float
    velocity_y_px_per_sec: float
    direction: str
    sample_count: int


class TrajectoryEstimator:
    """Estimate early ball motion from two or more timestamped positions.

    The estimator is intentionally stateless: callers own the bounded history
    and can request an estimate as soon as two detections exist. With three or
    more samples, a least-squares velocity fit smooths individual detection
    jitter without requiring a full shot history.
    """

    def __init__(
        self,
        frame_width: float,
        center_deadzone_px: float = DIRECTION_CENTER_DEADZONE_PX,
    ) -> None:
        if frame_width <= 0:
            raise ValueError("frame_width must be positive.")
        if center_deadzone_px < 0:
            raise ValueError("center_deadzone_px cannot be negative.")
        self._frame_width = float(frame_width)
        self._center_deadzone_px = float(center_deadzone_px)

    def estimate(self, history: Sequence[PositionSample]) -> TrajectoryEstimate | None:
        """Return a velocity estimate, or ``None`` until two samples exist.

        Samples must be ordered oldest to newest and timestamps must be strictly
        increasing seconds from a monotonic clock.
        """
        if len(history) < 2:
            return None

        samples = tuple((float(x), float(y), float(timestamp)) for x, y, timestamp in history)
        timestamps = tuple(sample[2] for sample in samples)
        if any(later <= earlier for earlier, later in zip(timestamps, timestamps[1:])):
            raise ValueError("Position timestamps must be strictly increasing.")

        velocity_x = self._least_squares_slope(timestamps, tuple(sample[0] for sample in samples))
        velocity_y = self._least_squares_slope(timestamps, tuple(sample[1] for sample in samples))
        latest_x = samples[-1][0]
        return TrajectoryEstimate(
            speed_px_per_sec=hypot(velocity_x, velocity_y),
            angle_degrees=degrees(atan2(velocity_y, velocity_x)),
            velocity_x_px_per_sec=velocity_x,
            velocity_y_px_per_sec=velocity_y,
            direction=self.classify_horizontal_position(latest_x),
            sample_count=len(samples),
        )

    def classify_horizontal_position(self, x_position: float) -> str:
        """Classify the latest horizontal ball position as left, center, or right."""
        center_x = self._frame_width / 2.0
        if x_position < center_x - self._center_deadzone_px:
            return "left"
        if x_position > center_x + self._center_deadzone_px:
            return "right"
        return "center"

    @staticmethod
    def _least_squares_slope(timestamps: Sequence[float], values: Sequence[float]) -> float:
        """Return a per-second linear-fit slope for equally or unevenly spaced data."""
        mean_time = sum(timestamps) / len(timestamps)
        mean_value = sum(values) / len(values)
        time_variance = sum((timestamp - mean_time) ** 2 for timestamp in timestamps)
        if time_variance == 0:
            raise ValueError("Position timestamps must be distinct.")
        covariance = sum(
            (timestamp - mean_time) * (value - mean_value)
            for timestamp, value in zip(timestamps, values)
        )
        return covariance / time_variance
