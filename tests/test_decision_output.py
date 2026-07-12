from io import StringIO
import json

import pytest

from core.decision_output import DecisionEmitter


def test_stdout_mode_emits_one_json_line() -> None:
    stream = StringIO()
    emitter = DecisionEmitter(stream=stream)

    event = emitter.emit("left", latency_ms=102.5, budget_ms=800, deadline_met=True)

    assert event.direction == "LEFT"
    assert json.loads(stream.getvalue()) == {
        "direction": "LEFT",
        "latency_ms": 102.5,
        "budget_ms": 800.0,
        "deadline_met": True,
    }
    assert stream.getvalue().endswith("\n")


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, tuple[str, int]]] = []
        self.closed = False

    def sendto(self, payload: bytes, address: tuple[str, int]) -> None:
        self.sent.append((payload, address))

    def close(self) -> None:
        self.closed = True


def test_udp_mode_sends_the_same_json_line() -> None:
    fake_socket = FakeSocket()
    emitter = DecisionEmitter(
        udp_host="127.0.0.1",
        udp_port=9000,
        socket_factory=lambda *_: fake_socket,
    )

    emitter.emit("right", latency_ms=200, budget_ms=800, deadline_met=True)
    emitter.close()

    assert fake_socket.closed
    assert len(fake_socket.sent) == 1
    payload, address = fake_socket.sent[0]
    assert address == ("127.0.0.1", 9000)
    assert json.loads(payload) == {
        "direction": "RIGHT",
        "latency_ms": 200.0,
        "budget_ms": 800.0,
        "deadline_met": True,
    }


def test_udp_configuration_requires_host_and_port_together() -> None:
    with pytest.raises(ValueError, match="together"):
        DecisionEmitter(udp_host="127.0.0.1")
