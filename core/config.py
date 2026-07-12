"""Shared configuration placeholders for Reflex Keeper."""

# The single source of truth for the decision deadline.
REACTION_BUDGET_MS = 200
REACTION_DEFAULT_DELAY_MS = 100
MIN_SHOT_SPEED_PX_PER_SEC = 120.0

# Trajectory-estimation settings. Position timestamps are expressed in seconds.
DIRECTION_CENTER_DEADZONE_PX = 80.0

# Ball-detector settings. Tune these against the actual ball, camera position,
# and lighting before a live run. The white panels are deliberately excluded:
# the ball may be against a white background. Red wraps around the HSV hue
# boundary, so it needs two ranges.
BALL_HSV_RANGES = (
    ((10, 80, 80), (35, 255, 255)),    # yellow/orange panels
    ((0, 80, 80), (10, 255, 255)),     # low-hue red panels
    ((170, 80, 80), (180, 255, 255)),  # high-hue red panels
)
BALL_HSV_RANGE = BALL_HSV_RANGES[0]  # Backward-compatible single-range default.
BALL_MASK_CLOSE_KERNEL_SIZE = 5
# 1.5x expansion of the original initial lock-on area, centred in place.
INITIAL_BALL_ROI = (400, 300, 480, 360)  # x, y, width, height at 1280x720
BALL_MIN_RADIUS_PX = 5.0
BALL_MAX_RADIUS_PX = 60.0
BALL_MIN_CIRCULARITY = 0.50
BALL_MIN_SPEED_PX_PER_FRAME = 4.0
INITIAL_LAUNCH_MAX_DISPLACEMENT_PX = 240.0
RESTING_POSITION_GATE_PX = 50.0
LAUNCH_DIRECTION_MIN_COSINE = 0.70
TRACK_PREDICTION_GATE_PX = 75.0
TRACK_MIN_CONFIRMATIONS = 2
TRACK_MAX_MISSED_FRAMES = 2
TRACK_HISTORY_LENGTH = 32
KALMAN_PROCESS_NOISE = 5.0
KALMAN_MEASUREMENT_NOISE = 8.0

# macOS development camera settings. Verify against the connected webcam.
MAC_CAMERA_RESOLUTION = (1280, 720)
MAC_CAMERA_FPS = 30

# QNX CSI camera settings. Confirm sustainable end-to-end capture performance.
QNX_CAMERA_RESOLUTION = (1536, 864)
QNX_CAMERA_FPS = 120
