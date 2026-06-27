from __future__ import annotations
from typing import Any
from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .device import JHFanDevice

TIMER_NUMBER_DESCRIPTION = NumberEntityDescription(
    key="timingPowerOff1", translation_key="turn_off_timer", icon="mdi:timer-off",
    native_min_value=0, native_max_value=12, native_step=1, native_unit_of_measurement="h",
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    device = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([JHFanTimerEntity(device, entry, TIMER_NUMBER_DESCRIPTION)])

class JHFanTimerEntity(NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, device: JHFanDevice, entry: ConfigEntry, description: NumberEntityDescription) -> None:
        self._device = device
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{device.mac_address}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.mac_address)},
            "name": device.name, "manufacturer": "JH", "model": "Smart Fan",
        }
        self._attr_native_value = float(device.state.get("timingPowerOff1", 0))

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = float(self._device.state.get("timingPowerOff1", 0))
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._device.coordinator.async_config_entry_first_refresh()
        self.async_on_remove(self._device.coordinator.async_add_listener(self._handle_coordinator_update))

    async def async_set_native_value(self, value: float) -> None:
        await self._device.set_timer(int(value))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"mac_address": self._device.mac_address, "dp_key": "timingPowerOff1"}
