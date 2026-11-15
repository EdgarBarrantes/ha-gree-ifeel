"""The frames against a real remote's capture and the encoder that drove a real unit."""

import json
from pathlib import Path

import pytest

from custom_components.gree_ifeel.protocol import Fan, Mode, RemoteState, Vertical, ifeel_timings


def _decode(timings: list[int], start: int, count: int) -> int:
    value = 0
    for i in range(count):
        space = -timings[start + 2 * i + 1]
        value |= (space > 1100) << i
    return value


def test_ifeel_report() -> None:
    t = ifeel_timings(21)
    assert t[:2] == [6000, -3000]
    assert len(t) == 2 + 32 + 1
    assert _decode(t, 2, 8) == 21
    assert _decode(t, 18, 8) == 0xA5
    assert all(v > 0 for v in t[0::2]) and all(v < 0 for v in t[1::2])


@pytest.mark.parametrize("bad", [-1, 61])
def test_ifeel_range(bad: int) -> None:
    with pytest.raises(ValueError):
        ifeel_timings(bad)


def test_state_matches_remote_capture() -> None:
    # The remote's own frame: heat 16 °C, fan auto, flap at its last position, light and health
    # on, I Feel on: 0C 00 60 50 00 C4 00 20 | 0C 00 60 70 00 00 00 60
    a, b = RemoteState(mode=Mode.HEAT, set_point=16, light=True, health=True).blocks()
    assert bytes(a).hex(" ").upper() == "0C 00 60 50 00 C4 00 20"
    assert bytes(b).hex(" ").upper() == "0C 00 60 70 00 00 00 60"


def test_state_matches_proven_press() -> None:
    # The press that re-armed a real unit: heat 19, fan high, flap highest, light and health
    # off, followed by a report of 21.
    expected = json.loads((Path(__file__).parent / "press_19_high_up_report_21.json").read_text())
    press = RemoteState(
        mode=Mode.HEAT, set_point=19, fan=Fan.HIGH, vertical=Vertical.HIGHEST, light=False
    )
    assert press.timings(21) == expected


def test_ifeel_bit_off() -> None:
    a, _ = RemoteState(mode=Mode.COOL, set_point=24, ifeel=False).blocks()
    assert a[5] & 0x04 == 0


def test_swing_sets_auto_swing_bit() -> None:
    a, _ = RemoteState(mode=Mode.HEAT, set_point=22, vertical=Vertical.SWING).blocks()
    assert a[0] & 0x40 and a[4] & 0x0F == 1
