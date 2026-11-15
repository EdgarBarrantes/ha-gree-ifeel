"""Whether the unit follows the reports."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GreeIFeelConfigEntry
from .entity import GreeIFeelEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeIFeelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor (only with a climate entity to check against)."""
    if entry.runtime_data.climate:
        async_add_entities([FollowingSensor(entry, "following")])


class FollowingSensor(GreeIFeelEntity, BinarySensorEntity):
    """On while the unit's room temperature matches the reports; unknown while it is off."""

    @property
    def is_on(self) -> bool | None:
        """Whether the unit follows."""
        return self.reporter.following
