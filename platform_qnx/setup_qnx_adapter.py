"""Build the target-native CPython bridge with the QNX SDK's qcc compiler."""

from setuptools import Extension, setup


setup(
    name="reflex-qnx-camera",
    ext_modules=[
        Extension(
            "platform_qnx._sensor_camera",
            ["platform_qnx/_sensor_camera.c"],
            libraries=["camapi"],
        )
    ],
)
