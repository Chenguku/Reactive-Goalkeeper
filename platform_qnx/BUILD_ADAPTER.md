# Building the QNX adapter release artifact

This is a release-maintainer task, not a target setup step. The extension uses
CPython's stable ABI (`abi3`) and is named `_sensor_camera.abi3.so`, so one
artifact works across compatible CPython 3.8+ target versions on QNX AArch64.

1. On the QNX target image chosen for release, identify its Python header version and make the matching development headers available in the QNX SDK host sysroot.

2. On the QNX SDK host, source the SDK environment and point the build at that host-side header directory:

   ```sh
   source ~/qnx800/qnxsdp-env.sh
   export QNX_PYTHON_INCLUDE=/absolute/path/to/qnx/sysroot/usr/include/python3.x
   python3 platform_qnx/setup_qnx_adapter.py
   ```

3. Add the generated `platform_qnx/_sensor_camera.abi3.so` to the release bundle next to `camera_qnx.py`.

4. On a clean target image, run `python3 -m platform_qnx.preflight_qnx` before publishing the release bundle.
