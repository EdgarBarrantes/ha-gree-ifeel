"""The reporter end to end, with a fake emitter."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_capture_events, async_fire_time_changed

from custom_components.gree_ifeel.const import (
    CONF_AUTO_REARM,
    CONF_OFFSET,
    DOMAIN,
    EVENT_MISSED,
    EVENT_REARMED,
)
from custom_components.gree_ifeel.protocol import Fan, Mode, RemoteState, ifeel_timings
from custom_components.gree_ifeel.reporter import in_quiet_hours, report_value

from .conftest import SENSOR, climate_state


def _is_report(timings: list[int]) -> bool:
    return timings[:2] == [6000, -3000]


def _is_press(timings: list[int]) -> bool:
    return timings[:2] == [9000, -4500]


async def _tick(hass: HomeAssistant, seconds: int = 121) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


def test_report_value() -> None:
    assert report_value(20.49, 0) == 20
    assert report_value(20.5, 0) == 21
    assert report_value(21.0, -0.5) == 21
    assert report_value(20.9, -0.5) == 20
    assert report_value(-3, 0) == 0


def test_quiet_hours() -> None:
    from datetime import time

    assert in_quiet_hours(time(23), time(22), time(8))
    assert in_quiet_hours(time(7, 59), time(22), time(8))
    assert not in_quiet_hours(time(12), time(22), time(8))
    assert in_quiet_hours(time(13), time(12), time(14))
    assert not in_quiet_hours(time(13), time(12), time(12))


async def test_reports_and_follows(hass: HomeAssistant, emitter, entry) -> None:
    hass.states.async_set(SENSOR, "20.6")
    climate_state(hass, current=19)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch("custom_components.gree_ifeel.reporter.VERIFY_AFTER", 0):
        await _tick(hass)
        assert emitter.sent[-1] == ifeel_timings(21)
        climate_state(hass, current=21)  # the unit refreshed and took it
        await _tick(hass)

    assert hass.states.get("binary_sensor.i_feel_gree_following_reports").state == "on"
    assert hass.states.get("sensor.i_feel_gree_reported_temperature").state == "21"
    assert hass.states.get("sensor.i_feel_gree_missed_reports").state == "0"


async def test_send_on_change(hass: HomeAssistant, emitter, entry, freezer) -> None:
    hass.states.async_set(SENSOR, "20.2")
    climate_state(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _tick(hass)
    assert emitter.sent[-1] == ifeel_timings(20)
    hass.states.async_set(SENSOR, "20.8")  # within 30 s of the report: waits for the round
    await hass.async_block_till_done()
    assert emitter.sent[-1] == ifeel_timings(20)
    freezer.tick(timedelta(seconds=40))
    hass.states.async_set(SENSOR, "20.7")
    await hass.async_block_till_done()
    assert emitter.sent[-1] == ifeel_timings(21)


async def test_rearms_when_ignored(hass: HomeAssistant, emitter, entry) -> None:
    hass.states.async_set(SENSOR, "21")
    climate_state(hass, current=18)
    missed = async_capture_events(hass, EVENT_MISSED)
    rearmed = async_capture_events(hass, EVENT_REARMED)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch("custom_components.gree_ifeel.reporter.VERIFY_AFTER", 0),
        patch("custom_components.gree_ifeel.reporter.IFeelReporter._quiet", return_value=False),
    ):
        for _ in range(4):
            await _tick(hass)
            climate_state(hass, current=18)  # refreshed, still its own sensor

    assert len(missed) == 1
    assert len(rearmed) == 1
    presses = [t for t in emitter.sent if _is_press(t)]
    assert len(presses) == 1
    # mode and set point (heat, 19) and fan (high) from the climate entity, I Feel on, then a report
    expected = RemoteState(mode=Mode.HEAT, set_point=19, fan=Fan.HIGH).timings(21)
    assert presses[0] == expected
    assert hass.states.get("binary_sensor.i_feel_gree_following_reports").state == "off"


async def test_no_rearm_in_quiet_hours_or_when_off(hass: HomeAssistant, emitter, entry) -> None:
    hass.states.async_set(SENSOR, "21")
    climate_state(hass, current=18)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    with (
        patch("custom_components.gree_ifeel.reporter.VERIFY_AFTER", 0),
        patch("custom_components.gree_ifeel.reporter.IFeelReporter._quiet", return_value=True),
    ):
        for _ in range(5):
            await _tick(hass)
            climate_state(hass, current=18)
    assert not [t for t in emitter.sent if _is_press(t)]

    climate_state(hass, mode="off")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.i_feel_gree_re_arm_i_feel"}, blocking=True
        )


async def test_repair_issue_without_auto_rearm(hass: HomeAssistant, emitter, entry) -> None:
    hass.config_entries.async_update_entry(entry, options={CONF_AUTO_REARM: False})
    hass.states.async_set(SENSOR, "21")
    climate_state(hass, current=18)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    with patch("custom_components.gree_ifeel.reporter.VERIFY_AFTER", 0):
        for _ in range(5):
            await _tick(hass)
            climate_state(hass, current=18)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"not_following_{entry.entry_id}")
    assert issue is not None
    assert not [t for t in emitter.sent if _is_press(t)]

    with patch("custom_components.gree_ifeel.reporter.VERIFY_AFTER", 0):
        climate_state(hass, current=21)
        await _tick(hass)
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"not_following_{entry.entry_id}") is None


async def test_paused_while_off(hass: HomeAssistant, emitter, entry) -> None:
    hass.states.async_set(SENSOR, "21")
    climate_state(hass, mode="off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _tick(hass)
    assert emitter.sent == []


async def test_switch_off_stops_reports(hass: HomeAssistant, emitter, entry) -> None:
    hass.config_entries.async_update_entry(entry, options={CONF_OFFSET: -0.5})
    hass.states.async_set(SENSOR, "21")
    climate_state(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.i_feel_gree_reporting"}, blocking=True
    )
    await _tick(hass)
    assert emitter.sent == []
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.i_feel_gree_reporting"}, blocking=True
    )
    assert emitter.sent[-1] == ifeel_timings(21)  # 21 - 0.5 rounds up to 21


async def test_emitter_failure_counts_as_miss(hass: HomeAssistant, emitter, entry) -> None:
    hass.states.async_set(SENSOR, "21")
    climate_state(hass)
    missed = async_capture_events(hass, EVENT_MISSED)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    emitter.fail = True
    for _ in range(3):
        await _tick(hass)
    assert len(missed) == 1
