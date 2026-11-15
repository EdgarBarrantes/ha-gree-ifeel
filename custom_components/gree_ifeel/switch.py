"""Reporting on / off."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import GreeIFeelConfigEntry
from .entity import GreeIFeelEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeIFeelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the reporting switch."""
    async_add_entities([ReportingSwitch(entry, "reporting")])


class ReportingSwitch(GreeIFeelEntity, SwitchEntity, RestoreEntity):
    """Turns the reports off without removing the entry (for example to use the real remote)."""

    async def async_added_to_hass(self) -> None:
        """Restore the last state."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self.reporter.enabled = last.state != STATE_OFF

    @property
    def is_on(self) -> bool:
        """Whether reports are sent."""
        return self.reporter.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start sending, with a report right away."""
        self.reporter.enabled = True
        self.async_write_ha_state()
        await self.reporter.async_send_report()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop sending."""
        self.reporter.enabled = False
        self.async_write_ha_state()
