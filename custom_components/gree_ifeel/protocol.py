"""Gree infrared frames: the I Feel temperature report and the remote's state frame.

Both were checked against captures of a real Gree remote (YAN1F1 family) and a floor console that
steers by them. Timings follow Home Assistant's infrared convention: positive values are marks
(pulses), negative values are spaces, in microseconds, at 38 kHz.

I Feel report: header 6000 / 3000, then 2 bytes LSB first (byte 0 = whole degrees Celsius,
byte 1 = 0xA5) and a closing mark. The remote sends one every few minutes while I Feel is on.
The unit takes it silently (no beep) and steers by it instead of its own sensor.

State frame: what a remote button press sends, two 8-byte blocks in IRremoteESP8266's Gree layout
(header 9000 / 4500, a 3-bit link and 20 ms gap in each block, a nibble checksum). Its I Feel bit
(byte 5, bit 2) turns I Feel on. The unit beeps on it and, after a lapse, takes lone reports
again.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from infrared_protocols.commands import Command

MODULATION = 38000

_MARK = 660
_ZERO = 545
_ONE = 1647
_BLOCK_GAP = 40000

MIN_REPORT = 0
MAX_REPORT = 60
MIN_SET_POINT = 16
MAX_SET_POINT = 30


class Mode(IntEnum):
    """Operating modes in the state frame."""

    AUTO = 0
    COOL = 1
    DRY = 2
    FAN_ONLY = 3
    HEAT = 4


class Fan(IntEnum):
    """Fan speeds in the state frame."""

    AUTO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class Vertical(IntEnum):
    """Vertical flap (byte 4, low nibble)."""

    LAST = 0
    SWING = 1
    HIGHEST = 2
    HIGH = 3
    MIDDLE = 4
    LOW = 5
    LOWEST = 6


def _bits(out: list[int], value: int, count: int = 8) -> None:
    for i in range(count):
        out += [_MARK, -(_ONE if value >> i & 1 else _ZERO)]


def ifeel_timings(celsius: int) -> list[int]:
    """Timings of an I Feel report of a whole-degree temperature."""
    if not MIN_REPORT <= celsius <= MAX_REPORT:
        raise ValueError(f"temperature {celsius} out of range {MIN_REPORT}..{MAX_REPORT}")
    out = [6000, -3000]
    _bits(out, celsius)
    _bits(out, 0xA5)
    return [*out, _MARK]


def _checksum(block: list[int]) -> list[int]:
    total = 10 + sum(b & 0xF for b in block[:4]) + sum(b >> 4 for b in block[4:7])
    block[7] = (block[7] & 0x0F) | ((total & 0xF) << 4)
    return block


def _block_timings(block: list[int]) -> list[int]:
    out = [9000, -4500]
    for b in block[:4]:
        _bits(out, b)
    _bits(out, 0b010, 3)
    out += [_MARK, -20000]
    for b in block[4:]:
        _bits(out, b)
    return [*out, _MARK]


@dataclass(frozen=True, kw_only=True)
class RemoteState:
    """What a remote button press tells the unit; every press carries all of it."""

    mode: Mode
    set_point: int
    fan: Fan = Fan.AUTO
    vertical: Vertical = Vertical.LAST
    light: bool = True
    health: bool = False
    turbo: bool = False
    xfan: bool = False
    sleep: bool = False
    ifeel: bool = True

    def blocks(self) -> tuple[list[int], list[int]]:
        """The two 8-byte blocks of the state frame."""
        if not MIN_SET_POINT <= self.set_point <= MAX_SET_POINT:
            raise ValueError(
                f"set point {self.set_point} out of range {MIN_SET_POINT}..{MAX_SET_POINT}"
            )
        b0 = (
            self.mode
            | 0x08  # power on
            | self.fan << 4
            | (0x40 if self.vertical is Vertical.SWING else 0)
            | (0x80 if self.sleep else 0)
        )
        b2 = (
            (0x10 if self.turbo else 0)
            | (0x20 if self.light else 0)
            | (0x40 if self.health else 0)
            | (0x80 if self.xfan else 0)
        )
        b5 = 0xC0 | (0x04 if self.ifeel else 0)
        a = _checksum([b0, self.set_point - 16, b2, 0x50, self.vertical, b5, 0x00, 0x00])
        b = _checksum([b0, self.set_point - 16, b2, 0x70, self.vertical, 0x00, 0x00, 0x00])
        return a, b

    def timings(self, report: int | None = None) -> list[int]:
        """Timings of the press, followed by an I Feel report as the remote sends it."""
        a, b = self.blocks()
        out = [*_block_timings(a), -_BLOCK_GAP, *_block_timings(b)]
        if report is not None:
            out += [-_BLOCK_GAP, *ifeel_timings(report)]
        return out


class RawCommand(Command):
    """An infrared command from ready-made timings."""

    def __init__(self, timings: list[int], *, modulation: int = MODULATION) -> None:
        """Initialize the command."""
        super().__init__(modulation=modulation)
        self._timings = timings

    def get_raw_timings(self) -> list[int]:
        """Return the timings."""
        return list(self._timings)
