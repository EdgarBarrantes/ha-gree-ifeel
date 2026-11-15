"""Config and options flows."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.gree_ifeel.const import (
    CONF_CLIMATE,
    CONF_EMITTER,
    CONF_INTERVAL,
    CONF_OFFSET,
    CONF_SENSOR,
    DOMAIN,
)

from .conftest import CLIMATE, EMITTER, SENSOR


async def test_no_emitters(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"


async def test_user_flow_and_options(hass: HomeAssistant, emitter) -> None:
    hass.states.async_set(SENSOR, "21", {"device_class": "temperature"})
    hass.states.async_set(CLIMATE, "heat", {"friendly_name": "Living room AC"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMITTER: EMITTER, CONF_SENSOR: SENSOR, CONF_CLIMATE: CLIMATE}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "I Feel: Living room AC"
    entry = result["result"]
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "reports": {CONF_INTERVAL: 90, CONF_OFFSET: -0.5, "send_on_change": True, "only_when_on": True},
            "checking": {
                "verify": True,
                "misses_before_action": 3,
                "auto_rearm": True,
                "rearm_every_hours": 0,
                "quiet_start": "22:00:00",
                "quiet_end": "08:00:00",
            },
            "press": {
                "rearm_fan": "high",
                "rearm_vertical": "highest",
                "rearm_light": False,
                "rearm_health": False,
                "fallback_mode": "heat",
                "fallback_set_point": 22,
            },
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_INTERVAL] == 90
    assert entry.options[CONF_OFFSET] == -0.5
    assert entry.options["rearm_vertical"] == "highest"

    # the same emitter can't be set up twice
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMITTER: EMITTER, CONF_SENSOR: SENSOR}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
