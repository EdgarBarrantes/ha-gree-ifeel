"""Base entity for Gree I Feel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_UPDATE

if TYPE_CHECKING:
    from . import GreeIFeelConfigEntry


class GreeIFeelEntity(InfraredEmitterConsumerEntity):
    """An entity of a reporter; available while its infrared emitter is."""

    _attr_has_entity_name = True

    def __init__(self, entry: GreeIFeelConfigEntry, key: str) -> None:
        """Initialize the entity."""
        self.reporter = entry.runtime_data
        self._infrared_emitter_entity_id = self.reporter.emitter
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Gree",
            model="I Feel reporter",
        )

    async def async_added_to_hass(self) -> None:
        """Follow the reporter's updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE.format(self.reporter.entry.entry_id),
                self.async_write_ha_state,
            )
        )
