"""What was reported, what the unit reads, how many reports it missed."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GreeIFeelConfigEntry
from .entity import GreeIFeelEntity
from .reporter import IFeelReporter

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ReporterSensorDescription(SensorEntityDescription):
    """A sensor reading one of the reporter's values."""

    value: Callable[[IFeelReporter], float | int | datetime | None]


SENSORS = (
    ReporterSensorDescription(
        key="reported",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda r: r.last_sent,
    ),
    ReporterSensorDescription(
        key="unit_reading",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda r: r.ac_reading,
    ),
    ReporterSensorDescription(
        key="misses",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda r: r.misses,
    ),
    ReporterSensorDescription(
        key="last_report",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda r: r.last_sent_at,
    ),
    ReporterSensorDescription(
        key="last_rearm",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda r: r.last_rearm_at,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeIFeelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    async_add_entities(ReporterSensor(entry, d) for d in SENSORS)


class ReporterSensor(GreeIFeelEntity, SensorEntity):
    """One of the reporter's values."""

    entity_description: ReporterSensorDescription

    def __init__(self, entry: GreeIFeelConfigEntry, description: ReporterSensorDescription) -> None:
        """Initialize the sensor."""
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | datetime | None:
        """The value."""
        return self.entity_description.value(self.reporter)
