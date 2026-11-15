"""The reporter: sends I Feel reports, checks the unit follows them, re-arms it when it doesn't."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    HVACMode,
)
from homeassistant.components.infrared import async_send_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTO_REARM,
    CONF_CLIMATE,
    CONF_EMITTER,
    CONF_FALLBACK_MODE,
    CONF_FALLBACK_SET_POINT,
    CONF_FAN,
    CONF_HEALTH,
    CONF_INTERVAL,
    CONF_LIGHT,
    CONF_MISSES,
    CONF_OFFSET,
    CONF_ONLY_WHEN_ON,
    CONF_QUIET_END,
    CONF_QUIET_START,
    CONF_REARM_EVERY,
    CONF_SEND_ON_CHANGE,
    CONF_SENSOR,
    CONF_VERIFY,
    CONF_VERTICAL,
    DEFAULTS,
    DOMAIN,
    EVENT_FOLLOWING,
    EVENT_MISSED,
    EVENT_REARMED,
    FROM_CLIMATE,
    MAX_REARMS,
    REARM_COOLDOWN,
    SIGNAL_UPDATE,
    VERIFY_AFTER,
)
from .protocol import (
    MAX_REPORT,
    MAX_SET_POINT,
    MIN_REPORT,
    MIN_SET_POINT,
    Fan,
    Mode,
    RawCommand,
    RemoteState,
    Vertical,
    ifeel_timings,
)

_LOGGER = logging.getLogger(__name__)

_MODES = {
    HVACMode.HEAT: Mode.HEAT,
    HVACMode.COOL: Mode.COOL,
    HVACMode.DRY: Mode.DRY,
    HVACMode.FAN_ONLY: Mode.FAN_ONLY,
    HVACMode.AUTO: Mode.AUTO,
    HVACMode.HEAT_COOL: Mode.AUTO,
}
# Climate integrations name fan speeds differently; the infrared frame has four.
_FANS = {
    "auto": Fan.AUTO,
    "low": Fan.LOW,
    "quiet": Fan.LOW,
    "medium_low": Fan.LOW,
    "medium": Fan.MEDIUM,
    "middle": Fan.MEDIUM,
    "medium_high": Fan.HIGH,
    "high": Fan.HIGH,
    "turbo": Fan.HIGH,
}
# Changes of the sensor are sent at once, but not more often than this.
_MIN_GAP = timedelta(seconds=30)


def report_value(celsius: float, offset: float) -> int:
    """The whole degree a reading is reported as (halves round up, like the remote)."""
    value = int((celsius + offset) + 0.5) if celsius + offset >= 0 else 0
    return max(MIN_REPORT, min(MAX_REPORT, value))


def in_quiet_hours(now: time, start: time, end: time) -> bool:
    """Whether a time falls in the quiet hours (which may span midnight)."""
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


class IFeelReporter:
    """Sends a temperature sensor's readings to a Gree unit as I Feel reports."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the reporter."""
        self.hass = hass
        self.entry = entry
        self.enabled = True
        self.last_sent: int | None = None
        self.last_sent_at: datetime | None = None
        self.ac_reading: float | None = None
        self.misses = 0
        self.following: bool | None = None
        self.rearms = 0
        self.last_rearm_at: datetime | None = None
        self.last_error: str | None = None
        self._unsubs: list[Callable[[], None]] = []

    def _opt(self, key: str) -> Any:
        return self.entry.options.get(key, DEFAULTS[key])

    @property
    def emitter(self) -> str:
        """The infrared emitter entity."""
        return self.entry.data[CONF_EMITTER]

    @property
    def sensor(self) -> str:
        """The temperature sensor entity."""
        return self.entry.data[CONF_SENSOR]

    @property
    def climate(self) -> str | None:
        """The linked climate entity, if any."""
        return self.entry.data.get(CONF_CLIMATE) or None

    @property
    def threshold(self) -> int:
        """Missed reports in a row before acting."""
        return int(self._opt(CONF_MISSES))

    @callback
    def async_start(self) -> None:
        """Start the timer and, if enabled, sending on changes."""
        self._unsubs.append(
            async_track_time_interval(
                self.hass,
                self._async_tick,
                timedelta(seconds=int(self._opt(CONF_INTERVAL))),
                name=f"{DOMAIN} {self.entry.title}",
            )
        )
        if self._opt(CONF_SEND_ON_CHANGE):
            self._unsubs.append(
                async_track_state_change_event(self.hass, [self.sensor], self._async_sensor_changed)
            )

    @callback
    def async_stop(self) -> None:
        """Stop sending."""
        while self._unsubs:
            self._unsubs.pop()()

    @callback
    def _updated(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(self.entry.entry_id))

    def _climate_state(self) -> State | None:
        if not self.climate:
            return None
        state = self.hass.states.get(self.climate)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return state

    def _paused(self) -> bool:
        """Whether reports wait because the unit is off (when that option is on)."""
        if not self.climate or not self._opt(CONF_ONLY_WHEN_ON):
            return False
        state = self._climate_state()
        return state is None or state.state == HVACMode.OFF

    def _reading(self) -> float | None:
        state = self.hass.states.get(self.sensor)
        if state is None:
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    async def _async_tick(self, now: datetime | None = None) -> None:
        if not self.enabled:
            return
        if self._paused():
            if self.following is not None:
                self.following = None
                self.misses = 0
                self._updated()
            return
        self._evaluate()
        await self._async_act()
        await self.async_send_report()

    @callback
    def _async_sensor_changed(self, event: Event[EventStateChangedData]) -> None:
        if not self.enabled or self._paused():
            return
        reading = self._reading()
        if reading is None:
            return
        if report_value(reading, float(self._opt(CONF_OFFSET))) == self.last_sent:
            return
        if self.last_sent_at and dt_util.utcnow() - self.last_sent_at < _MIN_GAP:
            return
        self.entry.async_create_background_task(
            self.hass, self.async_send_report(), f"{DOMAIN} report on change"
        )

    def _evaluate(self) -> None:
        """Compare the unit's room temperature with the last report, once it has refreshed."""
        if not self._opt(CONF_VERIFY) or self.last_sent is None or self.last_sent_at is None:
            return
        state = self._climate_state()
        if state is None or state.attributes.get(ATTR_CURRENT_TEMPERATURE) is None:
            return
        if state.last_reported < self.last_sent_at + timedelta(seconds=VERIFY_AFTER):
            return  # not refreshed since the report: no verdict yet
        self.ac_reading = float(state.attributes[ATTR_CURRENT_TEMPERATURE])
        if round(self.ac_reading) == self.last_sent:
            if self.following is False:
                self.hass.bus.async_fire(EVENT_FOLLOWING, self._event_data())
            self.misses = 0
            self.rearms = 0
            self.following = True
            ir.async_delete_issue(self.hass, DOMAIN, f"not_following_{self.entry.entry_id}")
        else:
            self.misses += 1
            if self.misses == self.threshold:
                self.following = False
                self.hass.bus.async_fire(EVENT_MISSED, self._event_data())
        self._updated()

    def _event_data(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry.entry_id,
            "title": self.entry.title,
            "reported": self.last_sent,
            "unit_reading": self.ac_reading,
            "misses": self.misses,
        }

    def _quiet(self) -> bool:
        start = dt_util.parse_time(self._opt(CONF_QUIET_START))
        end = dt_util.parse_time(self._opt(CONF_QUIET_END))
        if start is None or end is None:
            return False
        return in_quiet_hours(dt_util.now().time(), start, end)

    async def _async_act(self) -> None:
        """Re-arm the unit when it stopped following, or on a schedule when it can't be checked."""
        now = dt_util.utcnow()
        if self.last_rearm_at and now - self.last_rearm_at < timedelta(seconds=REARM_COOLDOWN):
            return
        verifiable = self._verifiable()
        every = float(self._opt(CONF_REARM_EVERY))
        if verifiable and self.misses >= self.threshold:
            if not self._opt(CONF_AUTO_REARM) or self.rearms >= MAX_REARMS:
                self._raise_not_following()
                return
        elif not verifiable and every > 0:
            if self.last_rearm_at and now - self.last_rearm_at < timedelta(hours=every):
                return
            if self.last_rearm_at is None and self.last_sent_at is None:
                return  # first round after start: report first
        else:
            return
        if self._quiet():
            return
        try:
            await self.async_rearm()
        except HomeAssistantError as err:
            _LOGGER.warning("%s: re-arming failed: %s", self.entry.title, err)

    def _verifiable(self) -> bool:
        state = self._climate_state()
        return bool(
            self._opt(CONF_VERIFY)
            and state is not None
            and state.attributes.get(ATTR_CURRENT_TEMPERATURE) is not None
        )

    def _raise_not_following(self) -> None:
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"not_following_{self.entry.entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="not_following",
            translation_placeholders={
                "title": self.entry.title,
                "misses": str(self.misses),
                "rearms": str(self.rearms),
            },
        )

    async def async_send_report(self) -> None:
        """Send the sensor's current reading as an I Feel report."""
        reading = self._reading()
        if reading is None:
            _LOGGER.debug("%s: %s has no reading, nothing sent", self.entry.title, self.sensor)
            return
        value = report_value(reading, float(self._opt(CONF_OFFSET)))
        try:
            await async_send_command(self.hass, self.emitter, RawCommand(ifeel_timings(value)))
        except HomeAssistantError as err:
            self.last_error = str(err)
            self.misses += 1
            _LOGGER.warning("%s: sending a report failed: %s", self.entry.title, err)
            if self.misses == self.threshold:
                self.following = False
                self.hass.bus.async_fire(EVENT_MISSED, self._event_data())
            self._updated()
            return
        self.last_error = None
        self.last_sent = value
        self.last_sent_at = dt_util.utcnow()
        self._updated()

    def remote_state(self) -> RemoteState:
        """The state a re-arm press carries: the unit's, so the press changes nothing else."""
        state = self._climate_state()
        if self.climate and state is None:
            raise HomeAssistantError(f"{self.climate} is unavailable")
        if state is not None:
            if state.state == HVACMode.OFF:
                raise HomeAssistantError("the unit is off; a press would turn it on")
            mode = _MODES.get(HVACMode(state.state), Mode.HEAT)
            target = state.attributes.get(ATTR_TEMPERATURE)
            set_point = round(float(target)) if target is not None else None
        else:
            mode = _MODES[HVACMode(self._opt(CONF_FALLBACK_MODE))]
            set_point = int(self._opt(CONF_FALLBACK_SET_POINT))
        if set_point is None:
            set_point = int(self._opt(CONF_FALLBACK_SET_POINT))
        set_point = max(MIN_SET_POINT, min(MAX_SET_POINT, set_point))
        fan_opt = self._opt(CONF_FAN)
        if fan_opt == FROM_CLIMATE:
            fan_name = (state.attributes.get(ATTR_FAN_MODE) if state else None) or "auto"
            fan = _FANS.get(str(fan_name).lower(), Fan.AUTO)
        else:
            fan = _FANS[fan_opt]
        return RemoteState(
            mode=mode,
            set_point=set_point,
            fan=fan,
            vertical=Vertical[str(self._opt(CONF_VERTICAL)).upper()],
            light=bool(self._opt(CONF_LIGHT)),
            health=bool(self._opt(CONF_HEALTH)),
        )

    async def async_rearm(self) -> None:
        """Send a remote press with I Feel on (the unit beeps once), then a report."""
        press = self.remote_state()
        reading = self._reading()
        report = None if reading is None else report_value(reading, float(self._opt(CONF_OFFSET)))
        await async_send_command(self.hass, self.emitter, RawCommand(press.timings(report)))
        self.rearms += 1
        self.last_rearm_at = dt_util.utcnow()
        if report is not None:
            self.last_sent = report
            self.last_sent_at = self.last_rearm_at
        _LOGGER.info("%s: re-armed I Feel (%s)", self.entry.title, press)
        self.hass.bus.async_fire(EVENT_REARMED, self._event_data())
        self._updated()
