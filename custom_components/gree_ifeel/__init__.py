"""Gree I Feel: send a room thermometer's readings to a Gree air conditioner over infrared."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .reporter import IFeelReporter

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]

type GreeIFeelConfigEntry = ConfigEntry[IFeelReporter]


async def async_setup_entry(hass: HomeAssistant, entry: GreeIFeelConfigEntry) -> bool:
    """Set up a reporter from a config entry."""
    reporter = IFeelReporter(hass, entry)
    entry.runtime_data = reporter
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    reporter.async_start()
    entry.async_on_unload(reporter.async_stop)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GreeIFeelConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
