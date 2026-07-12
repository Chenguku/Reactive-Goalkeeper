"""JSON-lines output for completed goalkeeper decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import socket
import sys
from typing import Callable, TextIO


@dataclass(frozen=True)
class DecisionEvent:
    """The serializable data emitted for a completed dive decision."""

    direction: str
    latency_ms: float
    budget_ms: float
    deadline_met: bool


class DecisionEmitter:
    """Emit decisions as one JSON object per line to stdout or UDP.

    UDP mode is intentionally connectionless: the visualization process may
    run separately and a missed display packet can never block the decision
    pipeline. Create one emitter per run and call :meth:`close` during
    teardown when UDP mode is active.
    """

    def __init__(
        self,
        *,
        udp_host: str | None = None,
        udp_port: int | None = None,
        stream: TextIO | None = None,
        socket_factory: Callable[..., socket.socket] = socket.socket,
    ) -> None:
        if (udp_host is None) != (udp_port is None):
            raise ValueError("udp_host and udp_port must be provided together.")
        if udp_port is not None and not 1 <= udp_port <= 65535:
            raise ValueError("udp_port must be between 1 and 65535.")

        self._stream = stream if stream is not None else sys.stdout
        self._udp_address = (udp_host, udp_port) if udp_host is not None else None
        self._socket = (
            socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
            if self._udp_address is not None
            else None
        )

    def emit(
        self,
        direction: str,
        latency_ms: float,
        budget_ms: float,
        deadline_met: bool,
    ) -> DecisionEvent:
        """Serialize and deliver one decision without rendering or formatting UI."""
        event = DecisionEvent(
            direction=direction.upper(),
            latency_ms=float(latency_ms),
            budget_ms=float(budget_ms),
            deadline_met=bool(deadline_met),
        )
        payload = json.dumps(asdict(event), separators=(",", ":")) + "\n"
        if self._socket is None:
            self._stream.write(payload)
            self._stream.flush()
        else:
            self._socket.sendto(payload.encode("utf-8"), self._udp_address)
        return event

    def close(self) -> None:
        """Release the optional UDP socket; stdout mode has nothing to close."""
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def __enter__(self) -> DecisionEmitter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
