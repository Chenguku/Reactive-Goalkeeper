"""QNX capture-to-decision pipeline with a FIFO-priority decision worker."""

from __future__ import annotations

from collections import deque
import ctypes
from dataclasses import dataclass
import os
from pathlib import Path
from queue import Empty, Queue
import sys
from threading import Event, Thread
from time import monotonic
from typing import Callable

# Allow `python platform_qnx/run_qnx.py` from the repository root.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.ball_detector import BallDetector
from core.camera_interface import Camera
from core.config import (
    QNX_CAPTURE_PRIORITY,
    QNX_DECISION_POLL_INTERVAL_MS,
    QNX_DECISION_PRIORITY,
    REACTION_BUDGET_MS,
    TRACK_HISTORY_LENGTH,
)
from core.decision_engine import Decision, DecisionEngine
from core.decision_output import DecisionEmitter
from core.trajectory import PositionSample, TrajectoryEstimate, TrajectoryEstimator
from platform_qnx.camera_qnx import QNXCamera, SensorFrameworkSource


class _SchedParam(ctypes.Structure):
    _fields_ = [("sched_priority", ctypes.c_int)]


def set_current_thread_scheduler(policy: int, priority: int) -> None:
    """Apply QNX scheduling policy to the current native Python thread.

    QNX schedules individual threads. ``pthread_setschedparam`` is therefore
    used instead of changing the whole process with ``sched_setscheduler``.
    """
    if not sys.platform.startswith("qnx"):
        raise RuntimeError("QNX real-time scheduling is only available on a QNX target.")

    libc = ctypes.CDLL(None, use_errno=True)
    pthread_self = libc.pthread_self
    pthread_self.restype = ctypes.c_void_p
    pthread_setschedparam = libc.pthread_setschedparam
    pthread_setschedparam.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(_SchedParam)]
    pthread_setschedparam.restype = ctypes.c_int

    result = pthread_setschedparam(
        pthread_self(), policy, ctypes.byref(_SchedParam(sched_priority=priority))
    )
    if result:
        raise OSError(
            result,
            "pthread_setschedparam failed; ensure the target grants the required QNX priority ability",
        )


@dataclass(frozen=True)
class _EstimateEvent:
    estimate: TrajectoryEstimate
    detected_at: float


@dataclass(frozen=True)
class _CommittedDecision:
    decision: Decision
    actual_latency_ms: float


class _DecisionClock:
    """Use a frame's capture timestamp for update, then monotonic time for polls."""

    def __init__(self, wall_clock: Callable[[], float]) -> None:
        self._wall_clock = wall_clock
        self.event_time: float | None = None

    def __call__(self) -> float:
        return self.event_time if self.event_time is not None else self._wall_clock()


class _DecisionWorker:
    """Receive estimates and commit one decision on a FIFO-priority thread."""

    _STOP = object()

    def __init__(
        self,
        emitter: DecisionEmitter,
        *,
        wall_clock: Callable[[], float],
        apply_scheduler: Callable[[int, int], None],
    ) -> None:
        self._emitter = emitter
        self._wall_clock = wall_clock
        self._apply_scheduler = apply_scheduler
        self._events: Queue[_EstimateEvent | object] = Queue()
        self._result: Queue[_CommittedDecision] = Queue(maxsize=1)
        self._ready = Event()
        self._stopped = Event()
        self._scheduler_error: BaseException | None = None
        self._thread = Thread(target=self._run, name="reflex-decision", daemon=True)

    def start(self) -> None:
        self._thread.start()
        self._ready.wait()
        if self._scheduler_error is not None:
            self._thread.join()
            raise RuntimeError("Unable to configure the QNX decision thread.") from self._scheduler_error

    def submit(self, estimate: TrajectoryEstimate, detected_at: float) -> None:
        self._events.put(_EstimateEvent(estimate, detected_at))

    def result(self) -> _CommittedDecision | None:
        try:
            return self._result.get_nowait()
        except Empty:
            return None

    def close(self) -> None:
        if not self._stopped.is_set():
            self._events.put(self._STOP)
        self._thread.join()

    def _run(self) -> None:
        try:
            self._apply_scheduler(os.SCHED_FIFO, QNX_DECISION_PRIORITY)
        except BaseException as error:
            self._scheduler_error = error
            self._ready.set()
            self._stopped.set()
            return

        self._ready.set()
        decision_clock = _DecisionClock(self._wall_clock)
        engine = DecisionEngine(clock=decision_clock)
        shot_detected_at: float | None = None
        poll_seconds = QNX_DECISION_POLL_INTERVAL_MS / 1000.0

        try:
            while True:
                try:
                    event = self._events.get(timeout=poll_seconds)
                except Empty:
                    event = None

                if event is self._STOP:
                    return

                if isinstance(event, _EstimateEvent):
                    decision_clock.event_time = event.detected_at
                    decision = engine.update(event.estimate)
                    if engine.shot_started and shot_detected_at is None:
                        shot_detected_at = event.detected_at
                    decision_clock.event_time = None
                else:
                    decision = engine.poll()

                if decision is None:
                    continue

                assert shot_detected_at is not None
                actual_latency_ms = max(0.0, (self._wall_clock() - shot_detected_at) * 1000.0)
                self._emitter.emit(
                    decision.direction,
                    latency_ms=actual_latency_ms,
                    budget_ms=REACTION_BUDGET_MS,
                    deadline_met=actual_latency_ms <= REACTION_BUDGET_MS,
                )
                self._result.put(_CommittedDecision(decision, actual_latency_ms))
                return
        finally:
            self._stopped.set()


def run_pipeline(
    camera: Camera,
    detector: BallDetector,
    trajectory_estimator: TrajectoryEstimator,
    emitter: DecisionEmitter,
    *,
    clock: Callable[[], float] = monotonic,
    apply_scheduler: Callable[[int, int], None] = set_current_thread_scheduler,
) -> Decision:
    """Capture one shot at normal priority and emit one FIFO-thread decision."""
    # Deliberately keep capture/detection below the decision worker so a slow
    # frame read or OpenCV operation cannot run at the real-time priority.
    apply_scheduler(os.SCHED_OTHER, QNX_CAPTURE_PRIORITY)

    history: deque[PositionSample] = deque(maxlen=TRACK_HISTORY_LENGTH)
    previous_state = detector.tracking_state
    last_detection: PositionSample | None = None
    worker = _DecisionWorker(emitter, wall_clock=clock, apply_scheduler=apply_scheduler)
    worker.start()

    try:
        while True:
            committed = worker.result()
            if committed is not None:
                return committed.decision

            frame = camera.read_frame()
            timestamp = clock()
            detection = detector.detect(frame)
            state = detector.tracking_state

            if state == "tracking":
                if previous_state != "tracking":
                    history.clear()
                    if last_detection is not None:
                        history.append(last_detection)
                if detection is not None:
                    history.append((detection.position[0], detection.position[1], timestamp))
                    estimate = trajectory_estimator.estimate(tuple(history))
                    if estimate is not None:
                        worker.submit(estimate, timestamp)
            elif state == "searching":
                history.clear()

            if detection is not None:
                last_detection = (detection.position[0], detection.position[1], timestamp)
            previous_state = state
    finally:
        worker.close()


def main() -> None:
    """Construct the Sensor Framework-backed QNX pipeline for one shot."""
    camera = QNXCamera(SensorFrameworkSource())
    emitter = DecisionEmitter()
    try:
        run_pipeline(
            camera,
            BallDetector(),
            TrajectoryEstimator(frame_width=camera.resolution[0]),
            emitter,
        )
    except KeyboardInterrupt:
        pass
    finally:
        emitter.close()
        camera.close()


if __name__ == "__main__":
    main()
