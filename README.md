# Reflex Keeper

Reflex Keeper is a real-time simulated goalkeeper for incoming penalty shots.
It detects the ball, estimates its trajectory, and produces a left, center, or right dive decision within a fixed reaction budget.
The shared core remains platform-agnostic, with a best-effort macOS development target and a QNX target intended for deterministic scheduling.
Visualization is intentionally separate from the critical capture-to-decision pipeline; on QNX, verify package availability and install dependencies with `apk add` rather than `pip`.
