"""Layered, trajectory-gated detector for one known ball."""

from dataclasses import dataclass
from collections import deque

import cv2
import numpy as np

from core.config import (
    BALL_HSV_RANGE,
    BALL_HSV_RANGES,
    BALL_MAX_RADIUS_PX,
    BALL_MASK_CLOSE_KERNEL_SIZE,
    BALL_MIN_CIRCULARITY,
    BALL_MIN_RADIUS_PX,
    BALL_MIN_SPEED_PX_PER_FRAME,
    INITIAL_BALL_ROI,
    INITIAL_LAUNCH_MAX_DISPLACEMENT_PX,
    KALMAN_MEASUREMENT_NOISE,
    KALMAN_PROCESS_NOISE,
    LAUNCH_DIRECTION_MIN_COSINE,
    RESTING_POSITION_GATE_PX,
    TRACK_MAX_MISSED_FRAMES,
    TRACK_HISTORY_LENGTH,
    TRACK_MIN_CONFIRMATIONS,
    TRACK_PREDICTION_GATE_PX,
)


@dataclass(frozen=True)
class BallDetection:
    """A ball location accepted by the detector."""

    position: tuple[float, float]
    radius: float
    confidence: float


@dataclass(frozen=True)
class _Candidate:
    position: tuple[float, float]
    radius: float
    circularity: float


class BallDetector:
    """Detect one configured ball using appearance, geometry, and motion."""

    def __init__(
        self,
        *,
        hsv_range: tuple[tuple[int, int, int], tuple[int, int, int]] | None = None,
        hsv_ranges: tuple[tuple[tuple[int, int, int], tuple[int, int, int]], ...] = BALL_HSV_RANGES,
        initial_roi: tuple[int, int, int, int] = INITIAL_BALL_ROI,
        min_radius_px: float = BALL_MIN_RADIUS_PX,
        max_radius_px: float = BALL_MAX_RADIUS_PX,
        min_circularity: float = BALL_MIN_CIRCULARITY,
        min_speed_px_per_frame: float = BALL_MIN_SPEED_PX_PER_FRAME,
        initial_launch_max_displacement_px: float = INITIAL_LAUNCH_MAX_DISPLACEMENT_PX,
        resting_position_gate_px: float = RESTING_POSITION_GATE_PX,
        launch_direction_min_cosine: float = LAUNCH_DIRECTION_MIN_COSINE,
        prediction_gate_px: float = TRACK_PREDICTION_GATE_PX,
        min_confirmations: int = TRACK_MIN_CONFIRMATIONS,
        max_missed_frames: int = TRACK_MAX_MISSED_FRAMES,
        process_noise: float = KALMAN_PROCESS_NOISE,
        measurement_noise: float = KALMAN_MEASUREMENT_NOISE,
    ) -> None:
        active_hsv_ranges = (hsv_range,) if hsv_range is not None else hsv_ranges
        self._hsv_ranges = tuple(
            (np.array(lower, dtype=np.uint8), np.array(upper, dtype=np.uint8))
            for lower, upper in active_hsv_ranges
        )
        self._initial_roi = initial_roi
        self._min_radius_px = min_radius_px
        self._max_radius_px = max_radius_px
        self._min_circularity = min_circularity
        self._min_speed_px_per_frame = min_speed_px_per_frame
        self._initial_launch_max_displacement_px = initial_launch_max_displacement_px
        self._resting_position_gate_px = resting_position_gate_px
        self._launch_direction_min_cosine = launch_direction_min_cosine
        self._prediction_gate_px = prediction_gate_px
        self._min_confirmations = min_confirmations
        self._max_missed_frames = max_missed_frames
        self._process_noise = process_noise
        self._measurement_noise = measurement_noise
        self.reset()

    @property
    def predicted_position(self) -> tuple[float, float] | None:
        """Return the prediction used to gate the most recent tracked frame."""
        if self._last_prediction is None:
            return None
        return tuple(float(value) for value in self._last_prediction)

    @property
    def prediction_gate_px(self) -> float:
        """Return the radius of the active predicted-region gate."""
        return self._prediction_gate_px

    @property
    def tracking_state(self) -> str:
        """Return ``searching``, ``resting``, or ``tracking`` for the current shot."""
        if self._in_flight:
            return "tracking"
        if self._last_measurement is not None:
            return "resting"
        return "searching"

    @property
    def resting_position(self) -> tuple[float, float] | None:
        """Return the last ball position locked before launch, if available."""
        if self._in_flight or self._last_measurement is None:
            return None
        return tuple(float(value) for value in self._last_measurement)

    @property
    def trajectory(self) -> tuple[tuple[float, float], ...]:
        """Return recent accepted ball centroids for diagnostics and rendering."""
        return tuple(self._trajectory)

    def reset(self) -> None:
        """Discard the current shot's lock and temporal state."""
        self._state: np.ndarray | None = None
        self._covariance: np.ndarray | None = None
        self._last_measurement: np.ndarray | None = None
        self._confirmations = 0
        self._in_flight = False
        self._missed_frames = 0
        self._last_prediction: np.ndarray | None = None
        self._pending_launch: _Candidate | None = None
        self._trajectory: deque[tuple[float, float]] = deque(maxlen=TRACK_HISTORY_LENGTH)

    def detect(self, frame: np.ndarray) -> BallDetection | None:
        """Return an accepted ball detection, or ``None`` for this frame."""
        candidates = self._find_candidates(frame)

        if not self._in_flight:
            candidate = self._choose_preflight_candidate(candidates, frame.shape)
            if candidate is None:
                return None
            return self._accept_preflight(candidate)

        predicted_position = self._predict()
        self._last_prediction = predicted_position
        candidate = self._choose_predicted_candidate(candidates, predicted_position)
        if candidate is None:
            self._missed_frames += 1
            if self._missed_frames > self._max_missed_frames:
                self.reset()
            return None

        self._update(candidate.position)
        self._last_measurement = np.array(candidate.position, dtype=float)
        self._confirmations += 1
        self._missed_frames = 0
        self._trajectory.append(candidate.position)
        return self._detection(candidate, predicted_position)

    def _find_candidates(self, frame: np.ndarray) -> list[_Candidate]:
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("Expected a BGR color frame with three channels.")

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lower, upper in self._hsv_ranges:
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lower, upper))
        close_kernel = np.ones(
            (BALL_MASK_CLOSE_KERNEL_SIZE, BALL_MASK_CLOSE_KERNEL_SIZE), dtype=np.uint8
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: list[_Candidate] = []

        for contour in contours:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            if area <= 0 or perimeter <= 0:
                continue
            circularity = 4.0 * np.pi * area / (perimeter * perimeter)
            (_, _), radius = cv2.minEnclosingCircle(contour)
            if not (
                self._min_radius_px <= radius <= self._max_radius_px
                and circularity >= self._min_circularity
            ):
                continue
            moments = cv2.moments(contour)
            if moments["m00"] == 0:
                continue
            candidates.append(
                _Candidate(
                    position=(moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]),
                    radius=radius,
                    circularity=float(circularity),
                )
            )
        return candidates

    def _choose_preflight_candidate(
        self, candidates: list[_Candidate], frame_shape: tuple[int, ...]
    ) -> _Candidate | None:
        if self._last_measurement is None:
            roi_candidates = [
                candidate
                for candidate in candidates
                if self._in_initial_roi(candidate.position, frame_shape)
            ]
            return self._best_candidate(roi_candidates)

        resting_candidates = [
            candidate
            for candidate in candidates
            if self._distance(candidate.position, self._last_measurement)
            <= self._resting_position_gate_px
        ]
        resting_candidate = self._best_candidate(resting_candidates, self._last_measurement)
        if resting_candidate is not None:
            self._pending_launch = None
            return resting_candidate

        launch_candidates = []
        for candidate in candidates:
            displacement = self._distance(candidate.position, self._last_measurement)
            if self._min_speed_px_per_frame <= displacement <= self._initial_launch_max_displacement_px:
                launch_candidates.append(candidate)

        launch_candidate = self._best_candidate(launch_candidates, self._last_measurement)
        if launch_candidate is None:
            self._pending_launch = None
            return None

        # A single distant color match must not steal the resting-ball lock.
        # Require a second candidate whose motion continues in the same direction.
        if self._pending_launch is None:
            self._pending_launch = launch_candidate
            return None
        if self._continues_pending_launch(launch_candidate):
            self._pending_launch = None
            return launch_candidate

        self._pending_launch = launch_candidate
        return None

    def _continues_pending_launch(self, candidate: _Candidate) -> bool:
        assert self._pending_launch is not None and self._last_measurement is not None
        first_motion = np.array(self._pending_launch.position) - self._last_measurement
        next_motion = np.array(candidate.position) - np.array(self._pending_launch.position)
        first_length = np.linalg.norm(first_motion)
        next_length = np.linalg.norm(next_motion)
        if next_length < self._min_speed_px_per_frame:
            return False
        direction_cosine = float(np.dot(first_motion, next_motion) / (first_length * next_length))
        return direction_cosine >= self._launch_direction_min_cosine

    def _accept_preflight(self, candidate: _Candidate) -> BallDetection:
        """Keep the resting ball visible until its motion starts a tracked shot."""
        measurement = np.array(candidate.position, dtype=float)
        if self._last_measurement is None:
            self._last_measurement = measurement
            self._confirmations = 1
            self._trajectory.append(candidate.position)
            return self._detection(candidate)

        velocity = measurement - self._last_measurement
        self._confirmations += 1
        if (
            self._confirmations >= self._min_confirmations
            and np.linalg.norm(velocity) >= self._min_speed_px_per_frame
        ):
            self._state = np.array([measurement[0], measurement[1], velocity[0], velocity[1]])
            self._covariance = np.eye(4, dtype=float) * self._measurement_noise
            self._in_flight = True
        self._last_measurement = measurement
        self._trajectory.append(candidate.position)
        return self._detection(candidate)

    def _choose_predicted_candidate(
        self, candidates: list[_Candidate], predicted_position: np.ndarray
    ) -> _Candidate | None:
        valid = []
        for candidate in candidates:
            speed = self._distance(candidate.position, self._last_measurement)
            prediction_error = self._distance(candidate.position, predicted_position)
            if speed >= self._min_speed_px_per_frame and prediction_error <= self._prediction_gate_px:
                valid.append(candidate)
        return self._best_candidate(valid, predicted_position)

    def _predict(self) -> np.ndarray:
        assert self._state is not None and self._covariance is not None
        transition = np.array(
            [[1.0, 0.0, 1.0, 0.0], [0.0, 1.0, 0.0, 1.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
        )
        self._state = transition @ self._state
        self._covariance = transition @ self._covariance @ transition.T + np.eye(4) * self._process_noise
        return self._state[:2].copy()

    def _update(self, position: tuple[float, float]) -> None:
        assert self._state is not None and self._covariance is not None
        observation = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])
        innovation = np.array(position) - observation @ self._state
        innovation_covariance = observation @ self._covariance @ observation.T + np.eye(2) * self._measurement_noise
        gain = self._covariance @ observation.T @ np.linalg.inv(innovation_covariance)
        self._state = self._state + gain @ innovation
        self._covariance = (np.eye(4) - gain @ observation) @ self._covariance

    def _in_initial_roi(self, position: tuple[float, float], frame_shape: tuple[int, ...]) -> bool:
        x, y, width, height = self._initial_roi
        frame_height, frame_width = frame_shape[:2]
        x_end = min(x + width, frame_width)
        y_end = min(y + height, frame_height)
        return x <= position[0] < x_end and y <= position[1] < y_end

    def _best_candidate(
        self, candidates: list[_Candidate], predicted_position: np.ndarray | None = None
    ) -> _Candidate | None:
        if not candidates:
            return None
        if predicted_position is None:
            return max(candidates, key=lambda candidate: candidate.circularity)
        return min(
            candidates,
            key=lambda candidate: self._distance(candidate.position, predicted_position),
        )

    def _detection(
        self, candidate: _Candidate, predicted_position: np.ndarray | None = None
    ) -> BallDetection:
        confidence = candidate.circularity
        if predicted_position is not None:
            confidence *= max(
                0.0,
                1.0 - self._distance(candidate.position, predicted_position) / self._prediction_gate_px,
            )
        return BallDetection(candidate.position, candidate.radius, float(confidence))

    @staticmethod
    def _distance(position: tuple[float, float], reference: np.ndarray) -> float:
        return float(np.linalg.norm(np.array(position, dtype=float) - reference))
