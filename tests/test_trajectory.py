import math

import pytest

from core.trajectory import TrajectoryEstimator


def test_two_samples_produce_an_early_velocity_estimate() -> None:
    estimator = TrajectoryEstimator(frame_width=1280, center_deadzone_px=80)

    estimate = estimator.estimate(((500, 300, 1.0), (530, 340, 1.1)))

    assert estimate is not None
    assert estimate.sample_count == 2
    assert estimate.velocity_x_px_per_sec == pytest.approx(300)
    assert estimate.velocity_y_px_per_sec == pytest.approx(400)
    assert estimate.speed_px_per_sec == pytest.approx(500)
    assert estimate.angle_degrees == pytest.approx(53.13, abs=0.01)
    assert estimate.direction == "left"


def test_three_samples_smooth_a_jittery_measurement() -> None:
    estimator = TrajectoryEstimator(frame_width=1280, center_deadzone_px=80)

    estimate = estimator.estimate(((600, 100, 0.0), (612, 112, 0.1), (620, 120, 0.2)))

    assert estimate is not None
    assert estimate.velocity_x_px_per_sec == pytest.approx(100)
    assert estimate.velocity_y_px_per_sec == pytest.approx(100)
    assert estimate.speed_px_per_sec == pytest.approx(math.sqrt(20_000))
    assert estimate.direction == "center"


def test_direction_uses_latest_position_and_center_deadzone() -> None:
    estimator = TrajectoryEstimator(frame_width=1000, center_deadzone_px=100)

    assert estimator.estimate(((200, 0, 0), (300, 0, 1))).direction == "left"
    assert estimator.estimate(((400, 0, 0), (500, 0, 1))).direction == "center"
    assert estimator.estimate(((700, 0, 0), (800, 0, 1))).direction == "right"


def test_one_sample_is_not_enough_for_velocity() -> None:
    assert TrajectoryEstimator(frame_width=1280).estimate(((500, 300, 1.0),)) is None


def test_rejects_non_increasing_timestamps() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        TrajectoryEstimator(frame_width=1280).estimate(((500, 300, 1.0), (530, 340, 1.0)))
