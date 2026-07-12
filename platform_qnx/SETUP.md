# QNX setup

1. Build and boot the QNX Raspberry Pi image with Sensor Framework and Camera Module 3 support. Confirm the camera using `camera_example3_viewfinder`.

2. On the QNX target, install the runtime modules:

   ```sh
   apk add opencv opencv-dev python3-numpy
   ```

3. On the QNX target, record the Python ABI values:

   ```sh
   python3 -c 'import sysconfig; print(sysconfig.get_config_var("INCLUDEPY")); print(sysconfig.get_config_var("LIBDIR")); print(sysconfig.get_config_var("LDLIBRARY")); print(sysconfig.get_config_var("EXT_SUFFIX"))'
   ```

4. On the QNX SDK host, source `qnxsdp-env.sh`. Set `QNX_PYTHON_INCLUDE` and `QNX_PYTHON_LIBDIR` to the corresponding **host-side QNX sysroot paths**, set `QNX_PYTHON_LIBRARY` to `LDLIBRARY` without `lib`/`.so`, and set `QNX_PYTHON_EXT_SUFFIX` to `EXT_SUFFIX`.

5. On the QNX SDK host, build the matching AArch64 extension:

   ```sh
   python3 platform_qnx/setup_qnx_adapter.py
   ```

6. Copy the generated `platform_qnx/_sensor_camera*.so` and the project to the QNX target.

7. On the QNX target, verify capture and BGR conversion:

   ```sh
   python3 -m platform_qnx.preflight_qnx
   ```

8. Run one live shot:

   ```sh
   python3 -m platform_qnx.run_qnx
   ```
