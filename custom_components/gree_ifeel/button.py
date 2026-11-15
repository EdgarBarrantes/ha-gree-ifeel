"""Send a report now; re-arm I Feel now."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GreeIFeelConfigEntry
from .entity import GreeIFeelEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeIFeelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons."""
    async_add_entities([ReportButton(entry, "send_report"), RearmButton(entry, "rearm")])


class ReportButton(GreeIFeelEntity, ButtonEntity):
    """Send the current reading now."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Send a report."""
        await self.reporter.async_send_report()


class RearmButton(GreeIFeelEntity, ButtonEntity):
    """A remote press with I Feel on: the unit beeps once and takes reports again."""

    async def async_press(self) -> None:
        """Re-arm I Feel."""
        await self.reporter.async_rearm()
