# QNX setup

1. Build and boot the prepared QNX Raspberry Pi image with Sensor Framework and Camera Module 3 support. Confirm the camera using `camera_example3_viewfinder`.

2. On the QNX target, install the runtime modules:

   ```sh
   apk add opencv opencv-dev python3-numpy
   ```

3. Copy the prepared Reflex Keeper release bundle to the target. It must include `platform_qnx/_sensor_camera.abi3.so`.

4. Verify Sensor Framework capture, the CPython adapter, and BGR conversion:

   ```sh
   python3 -m platform_qnx.preflight_qnx
   ```

5. Run one live shot:

   ```sh
   python3 -m platform_qnx.run_qnx
   ```
