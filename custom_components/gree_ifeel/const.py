"""Constants for Gree I Feel."""

from typing import Final

DOMAIN: Final = "gree_ifeel"

# Config entry data (reconfigure step)
CONF_EMITTER: Final = "infrared_emitter_entity_id"
CONF_SENSOR: Final = "temperature_sensor_entity_id"
CONF_CLIMATE: Final = "climate_entity_id"

# Options
CONF_INTERVAL: Final = "interval"
CONF_OFFSET: Final = "offset"
CONF_ONLY_WHEN_ON: Final = "only_when_on"
CONF_SEND_ON_CHANGE: Final = "send_on_change"
CONF_VERIFY: Final = "verify"
CONF_MISSES: Final = "misses_before_action"
CONF_AUTO_REARM: Final = "auto_rearm"
CONF_REARM_EVERY: Final = "rearm_every_hours"
CONF_QUIET_START: Final = "quiet_start"
CONF_QUIET_END: Final = "quiet_end"
CONF_FAN: Final = "rearm_fan"
CONF_VERTICAL: Final = "rearm_vertical"
CONF_LIGHT: Final = "rearm_light"
CONF_HEALTH: Final = "rearm_health"
CONF_FALLBACK_MODE: Final = "fallback_mode"
CONF_FALLBACK_SET_POINT: Final = "fallback_set_point"

# "From the climate entity": fan speed or mode follow the linked climate entity when it has one.
FROM_CLIMATE: Final = "climate"

FAN_OPTIONS: Final = [FROM_CLIMATE, "auto", "low", "medium", "high"]
VERTICAL_OPTIONS: Final = ["last", "swing", "highest", "high", "middle", "low", "lowest"]
MODE_OPTIONS: Final = ["heat", "cool", "dry", "fan_only", "auto"]

DEFAULTS: Final = {
    CONF_INTERVAL: 120,
    CONF_OFFSET: 0.0,
    CONF_ONLY_WHEN_ON: True,
    CONF_SEND_ON_CHANGE: True,
    CONF_VERIFY: True,
    CONF_MISSES: 3,
    CONF_AUTO_REARM: True,
    CONF_REARM_EVERY: 0,
    CONF_QUIET_START: "22:00:00",
    CONF_QUIET_END: "08:00:00",
    CONF_FAN: FROM_CLIMATE,
    CONF_VERTICAL: "last",
    CONF_LIGHT: True,
    CONF_HEALTH: False,
    CONF_FALLBACK_MODE: "heat",
    CONF_FALLBACK_SET_POINT: 22,
}

# A climate entity's report counts once it has been refreshed this long after a report went out.
VERIFY_AFTER: Final = 5
# A re-arm is not repeated sooner than this, so a unit out of reach is not beeped at every round.
REARM_COOLDOWN: Final = 1800
# After this many re-arms without the unit following, stop and raise a repair issue.
MAX_REARMS: Final = 3

EVENT_MISSED: Final = f"{DOMAIN}_not_following"
EVENT_REARMED: Final = f"{DOMAIN}_rearmed"
EVENT_FOLLOWING: Final = f"{DOMAIN}_following"

SIGNAL_UPDATE: Final = f"{DOMAIN}_update_{{}}"
