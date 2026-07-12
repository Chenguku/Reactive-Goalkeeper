# QNX Camera Module 3 setup

QNX on Raspberry Pi uses **Sensor Framework**, not V4L2, for the CSI-connected
Camera Module 3. Enable the Module 3 configuration and start the service using
the `sensor` command with `camera_module3.conf`; validate it first with
`camera_example3_viewfinder`. The QNX target image must include the Camera
Library (`libcamapi`) and Sensor Framework camera support. These are QNX SDP /
Quick Start Target Image components obtained through QNX Software Center, not
Python packages and not an `oss.qnx.com` download.

The repository includes that target-local binding as a CPython extension:
`platform_qnx/_sensor_camera.c`. It uses the Camera API viewfinder callback,
copies the latest NV12 frame, and returns it to `QNXCamera`, which converts it
to BGR before core detection runs. Build it on the QNX SDK host after sourcing
the QNX environment:

```sh
CC=qcc python3 platform_qnx/setup_qnx_adapter.py build_ext --inplace
```

Copy the generated `platform_qnx/_sensor_camera.*.so` into the same directory
on the target. No separate adapter project, V4L2 driver, or Python package is
required. A native build is unavoidable because QNX exposes this camera API as
C headers and `libcamapi`, not a Python module.

Install Python packages from QNX's externally-managed repository, never with
global `pip`. First verify the exact names available on the target, then install
the logical dependencies with commands such as `apk add opencv`.

Before running the goalkeeper pipeline, verify Sensor Framework actually
negotiates and sustains its active mode through Python conversion and the
detector. `QNXCamera` adopts the negotiated mode by default; set its
`require_requested_mode=True` only if you need strict enforcement of the
configured `1536x864 @ 120fps` target. The documented fallback remains
`2304x1296 @ 56fps` if you later need a fixed lower-rate configuration.
