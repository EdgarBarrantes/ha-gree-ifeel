"""Config flow for Gree I Feel."""

from __future__ import annotations

from typing import Any

import probatio
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.infrared import DOMAIN as INFRARED_DOMAIN
from homeassistant.components.infrared import async_get_emitters
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TimeSelector,
)

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
    FAN_OPTIONS,
    MODE_OPTIONS,
    VERTICAL_OPTIONS,
)

SECTIONS = {
    "reports": (CONF_INTERVAL, CONF_OFFSET, CONF_SEND_ON_CHANGE, CONF_ONLY_WHEN_ON),
    "checking": (CONF_VERIFY, CONF_MISSES, CONF_AUTO_REARM, CONF_REARM_EVERY, CONF_QUIET_START, CONF_QUIET_END),
    "press": (CONF_FAN, CONF_VERTICAL, CONF_LIGHT, CONF_HEALTH, CONF_FALLBACK_MODE, CONF_FALLBACK_SET_POINT),
}


def _number(lo: float, hi: float, step: float, unit: str | None = None) -> NumberSelector:
    config = NumberSelectorConfig(min=lo, max=hi, step=step, mode=NumberSelectorMode.BOX)
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


def _select(options: list[str], key: str) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(options=options, translation_key=key, mode=SelectSelectorMode.DROPDOWN)
    )


SELECTORS = {
    CONF_INTERVAL: _number(30, 600, 10, "s"),
    CONF_OFFSET: _number(-5, 5, 0.1, "°C"),
    CONF_SEND_ON_CHANGE: BooleanSelector(),
    CONF_ONLY_WHEN_ON: BooleanSelector(),
    CONF_VERIFY: BooleanSelector(),
    CONF_MISSES: _number(1, 20, 1),
    CONF_AUTO_REARM: BooleanSelector(),
    CONF_REARM_EVERY: _number(0, 24, 0.5, "h"),
    CONF_QUIET_START: TimeSelector(),
    CONF_QUIET_END: TimeSelector(),
    CONF_FAN: _select(FAN_OPTIONS, "fan"),
    CONF_VERTICAL: _select(VERTICAL_OPTIONS, "vertical"),
    CONF_LIGHT: BooleanSelector(),
    CONF_HEALTH: BooleanSelector(),
    CONF_FALLBACK_MODE: _select(MODE_OPTIONS, "mode"),
    CONF_FALLBACK_SET_POINT: _number(16, 30, 1, "°C"),
}


@callback
def _entities_schema(hass: HomeAssistant) -> probatio.Schema:
    return probatio.Schema(
        {
            probatio.Required(CONF_EMITTER): EntitySelector(
                EntitySelectorConfig(domain=INFRARED_DOMAIN, include_entities=async_get_emitters(hass))
            ),
            probatio.Required(CONF_SENSOR): EntitySelector(
                EntitySelectorConfig(domain=SENSOR_DOMAIN, device_class=SensorDeviceClass.TEMPERATURE)
            ),
            probatio.Optional(CONF_CLIMATE): EntitySelector(EntitySelectorConfig(domain=CLIMATE_DOMAIN)),
        }
    )


def _options_schema(options: dict[str, Any]) -> probatio.Schema:
    fields: dict[Any, Any] = {}
    for name, keys in SECTIONS.items():
        inner = {
            probatio.Required(key, default=options.get(key, DEFAULTS[key])): SELECTORS[key] for key in keys
        }
        fields[probatio.Required(name)] = section(probatio.Schema(inner), {"collapsed": name == "press"})
    return probatio.Schema(fields)


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in SECTIONS:
        out.update(user_input.get(name, {}))
    for key in (CONF_INTERVAL, CONF_MISSES, CONF_FALLBACK_SET_POINT):
        if key in out:
            out[key] = int(out[key])
    return out


class GreeIFeelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a reporter: an emitter facing the unit, a thermometer, optionally the unit's climate entity."""

    VERSION = 1

    def _name(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id)
        return state.name if state else entity_id

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the entities."""
        if not async_get_emitters(self.hass):
            return self.async_abort(reason="no_infrared_emitters")
        if user_input is not None:
            self._async_abort_entries_match({CONF_EMITTER: user_input[CONF_EMITTER]})
            target = user_input.get(CONF_CLIMATE) or user_input[CONF_EMITTER]
            return self.async_create_entry(title=f"I Feel: {self._name(target)}", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_entities_schema(self.hass))

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change the entities."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return self.async_update_reload_and_abort(entry, data=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(_entities_schema(self.hass), entry.data),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> GreeIFeelOptionsFlow:
        """Return the options flow."""
        return GreeIFeelOptionsFlow()


class GreeIFeelOptionsFlow(OptionsFlowWithReload):
    """How often to report, how to check and re-arm, and what the re-arm press carries."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the options."""
        if user_input is not None:
            return self.async_create_entry(data=_flatten(user_input))
        return self.async_show_form(step_id="init", data_schema=_options_schema(dict(self.config_entry.options)))
