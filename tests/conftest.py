"""Fixtures: a fake infrared emitter, a thermometer, a climate entity."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.components.infrared import InfraredCommand, InfraredEmitterEntity
from homeassistant.components.infrared.const import DATA_COMPONENT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gree_ifeel.const import CONF_CLIMATE, CONF_EMITTER, CONF_SENSOR, DOMAIN

EMITTER = "infrared.fake_emitter"
SENSOR = "sensor.living_room_temperature"
CLIMATE = "climate.gree"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> None:
    """Load integrations from custom_components."""


class FakeEmitter(InfraredEmitterEntity):
    """Records what it is asked to send."""

    _attr_name = "Fake emitter"
    _attr_unique_id = "fake_emitter"

    def __init__(self) -> None:
        self.sent: list[list[int]] = []
        self.fail = False

    async def async_send_command(self, command: InfraredCommand) -> None:
        from homeassistant.exceptions import HomeAssistantError

        if self.fail:
            raise HomeAssistantError("emitter offline")
        self.sent.append(command.get_raw_timings())


@pytest.fixture
async def emitter(hass: HomeAssistant) -> FakeEmitter:
    """A fake emitter registered with the infrared component."""
    assert await async_setup_component(hass, "infrared", {})
    entity = FakeEmitter()
    await hass.data[DATA_COMPONENT].async_add_entities([entity])
    await hass.async_block_till_done()
    return entity


def climate_state(hass: HomeAssistant, mode: str = "heat", current: float | None = 21, **attrs: Any) -> None:
    """Write the climate entity's state, as its integration would on each refresh."""
    hass.states.async_set(
        CLIMATE,
        mode,
        {"current_temperature": current, "temperature": 19, "fan_mode": "high", **attrs},
        force_update=True,
    )


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """A config entry with a climate entity."""
    e = MockConfigEntry(
        domain=DOMAIN,
        title="I Feel: Gree",
        data={CONF_EMITTER: EMITTER, CONF_SENSOR: SENSOR, CONF_CLIMATE: CLIMATE},
    )
    e.add_to_hass(hass)
    return e
