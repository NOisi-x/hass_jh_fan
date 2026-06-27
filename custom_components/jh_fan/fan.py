from __future__ import annotations
from typing import Any
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import percentage_to_ranged_value, ranged_value_to_percentage
from .const import DOMAIN
from .device import JHFanDevice

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    device = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([JHFanEntity(device, entry)])

class JHFanEntity(FanEntity):
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device: JHFanDevice, entry: ConfigEntry) -> None:
        self._device = device
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{device.mac_address}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.mac_address)},
            "name": device.name, "manufacturer": "JH", "model": "Smart Fan",
        }
        self._attr_supported_features = (
            FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
            | FanEntityFeature.SET_SPEED | FanEntityFeature.OSCILLATE
        )
        self._attr_is_on = device.is_on
        if self._attr_is_on:
            self._attr_percentage = self._speed_to_percentage(device.speed)
        else:
            self._attr_percentage = 0
        self._attr_oscillating = device.oscillation_horizontal

    @callback
    def _handle_coordinator_update(self) -> None:
        is_on = self._device.is_on
        self._attr_is_on = is_on
        if is_on:
            self._attr_percentage = self._speed_to_percentage(self._device.speed)
        else:
            self._attr_percentage = 0
        self._attr_oscillating = self._device.oscillation_horizontal
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._device.coordinator.async_config_entry_first_refresh()
        self.async_on_remove(self._device.coordinator.async_add_listener(self._handle_coordinator_update))

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        if percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self._device.set_power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.set_power(False)

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        speed = self._percentage_to_speed(percentage)
        if not self._attr_is_on:
            await self._device.set_power_and_speed(True, speed)
        else:
            await self._device.set_speed(speed)

    async def async_oscillate(self, oscillating: bool) -> None:
        await self._device.set_oscillation(horizontal=oscillating, vertical=self._device.oscillation_vertical)

    def _speed_range(self) -> tuple[int, int]:
        return (0, self._device.max_speed)

    @property
    def speed_count(self) -> int:
        return self._device.max_speed

    def _percentage_to_speed(self, percentage: int) -> int:
        if percentage == 0:
            return 0
        speed = int(percentage_to_ranged_value(self._speed_range(), percentage))
        return max(1, min(self._device.max_speed, speed))

    def _speed_to_percentage(self, speed: int) -> int:
        if speed == 0:
            return 0
        return int(ranged_value_to_percentage(self._speed_range(), speed))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self._device.state
        return {
            "mac_address": self._device.mac_address,
            "speed_level": self._device.speed,
            "timer_hours": state.get("timingPowerOff1", 0),
            "light": state.get("light_1", 0),
            "mosquito_mode": state.get("mosquitoControl", 0),
            "voice": state.get("voiceaAnnounce", 0),
        }
