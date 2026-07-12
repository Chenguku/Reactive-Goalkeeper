# Reactive Keeper

Reactive Keeper is a real-time simulated goalkeeper that detects when a soccer ball is shot, estimates its trajectory, and emits a left, center, or right dive decision within a reaction budget. The shared core is platform-neutral; macOS is the development target, while QNX is the deterministic deployment target.

## macOS commands

Install the Mac development dependencies first:

```sh
python3 -m pip install -r requirements.txt
```

| File | Command | What it does |
| --- | --- | --- |
| `platform_mac/camera_mac.py` | `python3 platform_mac/camera_mac.py` | Opens the MacBook webcam and shows a live preview. Press `q` or Escape to exit. |
| `platform_mac/live_detector_test.py` | `python3 platform_mac/live_detector_test.py` | Shows live ball-detection overlays, including the initial ROI, centroid, confidence, trajectory, and Kalman prediction gate. |
| `platform_mac/run_mac.py` | `python3 platform_mac/run_mac.py` | Runs one full capture → detect → trajectory → decision → JSON-output shot pipeline. |

For QNX installation, camera setup, the CPython camera bridge, preflight checks, and execution, see [platform_qnx/SETUP.md](platform_qnx/SETUP.md).
