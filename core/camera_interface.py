"""Platform-neutral camera backend contract."""

from abc import ABC, abstractmethod

import numpy as np


class Camera(ABC):
    """Interface implemented by each platform's camera backend."""

    @abstractmethod
    def read_frame(self) -> np.ndarray:
        """Return the next camera frame."""

    @property
    @abstractmethod
    def fps(self) -> float:
        """Return the configured capture frame rate."""

    @property
    @abstractmethod
    def resolution(self) -> tuple[int, int]:
        """Return the capture resolution as (width, height)."""
