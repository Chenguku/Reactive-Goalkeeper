"""Cross-build the QNX CPython camera extension with an explicit target ABI."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


REQUIRED_ENVIRONMENT = ("QNX_PYTHON_INCLUDE",)


def main() -> None:
    """Compile the extension against the copied target CPython development files."""
    missing = [name for name in REQUIRED_ENVIRONMENT if not os.environ.get(name)]
    if missing:
        names = ", ".join(missing)
        raise SystemExit(
            f"Missing {names}. Set it to the host-side QNX sysroot directory containing Python.h. "
            "See platform_qnx/BUILD_ADAPTER.md."
        )
    qcc = shutil.which("qcc")
    if qcc is None:
        raise SystemExit("qcc was not found; source qnxsdp-env.sh on the QNX SDK host first.")

    root = Path(__file__).resolve().parents[1]
    source = root / "platform_qnx" / "_sensor_camera.c"
    output = root / "platform_qnx" / "_sensor_camera.abi3.so"
    target = os.environ.get("QNX_QCC_TARGET", "gcc_ntoaarch64le")
    command = [
        qcc,
        f"-V{target}",
        "-shared",
        "-fPIC",
        f"-I{os.environ['QNX_PYTHON_INCLUDE']}",
        str(source),
        "-lcamapi",
        "-o",
        str(output),
    ]
    subprocess.run(command, check=True)
    print(output)


if __name__ == "__main__":
    main()
