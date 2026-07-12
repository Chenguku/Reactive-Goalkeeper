# AGENTS.md

## Project: Reflex Keeper — Real-Time Simulated Goalkeeper

A camera mounted at goalkeeper eye level watches an incoming penalty shot.
The system detects the ball, estimates its speed and direction, and outputs
a dive decision (left / center / right) within a fixed, consistent reaction
budget. The point of the project is the *consistency* of that budget —
QNX enforces it with real priority scheduling; the Mac build is a best-effort
dev/testing version with the same interfaces but no scheduling guarantees.

## Repo layout

```
core/               platform-agnostic logic — no camera I/O, no OS scheduling calls
  camera_interface.py   abstract Camera base class
  ball_detector.py       frame -> ball pixel position (+ confidence)
  trajectory.py           position history -> speed & direction estimate
  decision_engine.py     trajectory -> dive decision, deadline-aware
  decision_output.py     emits each decision (direction, latency) as JSON —
                          to stdout/log by default, network socket if configured
  config.py               shared constants (REACTION_BUDGET_MS, resolution, thresholds)

platform_mac/       macOS entrypoint + webcam backend (dev/test target)
platform_qnx/       QNX/Pi entrypoint + CSI camera backend (target build) —
                     capture, detect, decide, output only. No rendering here.
viz/                STRETCH GOAL, build last. Separate process (e.g. on the
                     laptop) that receives decision_output events over the
                     network and animates a goalie. Not required for the
                     core demo to work.
tests/              synthetic/offline tests for core/, no camera required
```

The v1 pipeline is: capture → detect → trajectory → decision → output.
Rendering is explicitly out of that pipeline — see "Out of scope" below.

## Hard constraints — do not change without discussion

1. `REACTION_BUDGET_MS` in `core/config.py` is the single source of truth for
   the deadline. Both platform entrypoints import it. Never hardcode a second
   copy anywhere else.
2. The decision engine must **always** emit a decision by the deadline, even
   degraded. If a full trajectory estimate isn't ready in time, fall back to
   the best partial estimate (e.g. direction-only, no speed) rather than
   blocking or throwing.
3. `core/` never imports platform-specific modules (no `cv2.VideoCapture`
   calls, no QNX scheduling APIs, no CSI camera libraries). Platform code
   calls into `core/`, never the reverse. This is what lets the same decision
   logic run identically on both platforms.
4. No network calls anywhere in the hot path (ball-detected → decision
   output). Anything cloud/API-based belongs in a separate layer, invoked
   only before the shot (setup) or after the decision is already displayed
   (explanation/commentary) — never in between.
5. Both platforms implement the same `Camera` interface
   (`read_frame()`, `fps`, `resolution`) so `core/` code is untouched when
   switching platforms.
6. `platform_qnx/` never depends on a rendering/graphics library (no pygame,
   no SDL). QNX's job is capture → detect → decide → output a direction and
   latency number — nothing else. Visualization, if built, runs as a
   separate process on separate hardware (see `viz/`) and only ever
   *receives* decision output; it's never in the critical path.

## Conventions

- Python 3.x. Minimal dependencies: opencv-python, numpy. On the QNX target,
  Python is externally managed (PEP 668) — install packages with
  `apk add py3-<name>` (Alpine Package Keeper, ported to QNX for the
  Developer Desktop), not pip. Check availability there before adding
  anything new — don't assume a pip package exists as an apk package too.
- `requirements.txt` at the repo root is the Mac/pip install path only —
  keep it in sync whenever a new dependency is added anywhere in core/ or
  platform_mac/. It is not the QNX install path (see above); don't
  reference it from platform_qnx/SETUP.md.
- All tunable values (color thresholds, reaction budget, resolution, camera
  index) live in `core/config.py`. No magic numbers in logic files.
- Ball detection: layer color threshold + shape/size filtering, gated by
  velocity magnitude and Kalman-predicted-region filtering (not plain
  frame-differencing — the kicker stays in motion post-kick, so "is it
  moving" alone isn't a valid ball/not-ball signal). Use a known-location
  ROI prior for first lock-on before a trajectory exists. Color alone has
  been unreliable in past attempts — don't collapse back to it. Full
  deep-learning detection (e.g. a quantized YOLO-nano) is an optional
  stretch upgrade only if the layered classical pipeline proves
  insufficient and there's time to spare; it's not the v1 baseline given
  QNX dependency risk and latency budget.
- Keep `decision_engine.py` and `trajectory.py` pure and unit-testable
  without a live camera.

## Out of scope for v1

- No physical actuator/servo — output is a direction + latency value.
- No on-Pi/on-QNX rendering — the core deliverable is the decision pipeline
  itself, provable via console/log output and the synthetic test harness.
- Goalie visualization (`viz/`) is a stretch goal, built only after the
  core pipeline works end-to-end on both Mac and QNX. If time runs out,
  the project still stands on its own without it.
- Single ball, single shot per run — no multi-object tracking.
- No cloud AI in the real-time decision path (see constraint 4).

## Testing

- `tests/synthetic_shot_test.py` feeds a recorded clip or synthetic ball
  trajectory through `core/` to validate detection + decision logic without
  a camera or QNX hardware.
- Get the Mac build correct first; port the same `core/` code to QNX and
  only then add real priority scheduling in `platform_qnx/`.
