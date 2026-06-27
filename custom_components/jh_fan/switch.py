from __future__ import annotations
from typing import Any
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .device import JHFanDevice

LIGHT_SWITCH_DESCRIPTION = SwitchEntityDescription(key="light_1", translation_key="ambient_light", icon="mdi:lightbulb")
MOSQUITO_SWITCH_DESCRIPTION = SwitchEntityDescription(key="mosquitoControl", translation_key="mosquito_mode", icon="mdi:mosquito")
VOICE_SWITCH_DESCRIPTION = SwitchEntityDescription(key="voiceaAnnounce", translation_key="voice_announcements", icon="mdi:volume-high")
VERTICAL_SWITCH_DESCRIPTION = SwitchEntityDescription(key="angleAutoUDOnOff", translation_key="vertical_oscillation", icon="mdi:arrow-up-down-bold")

_SWITCH_CONFIG = {
    "light_1": {"state_key": "light_1", "setter": lambda d, v: d.set_light(v)},
    "mosquitoControl": {"state_key": "mosquitoControl", "setter": lambda d, v: d.set_mosquito_mode(v)},
    "voiceaAnnounce": {"state_key": "voiceaAnnounce", "setter": lambda d, v: d.set_voice_announce(v)},
    "angleAutoUDOnOff": {"state_key": "angleAutoUDOnOff", "setter": lambda d, v: d.set_vertical_oscillation(v)},
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    device = hass.data[DOMAIN][entry.entry_id]
    entities = [
        JHFanSwitchEntity(device, entry, desc)
        for desc in [LIGHT_SWITCH_DESCRIPTION, MOSQUITO_SWITCH_DESCRIPTION, VOICE_SWITCH_DESCRIPTION, VERTICAL_SWITCH_DESCRIPTION]
    ]
    async_add_entities(entities)

class JHFanSwitchEntity(SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, device: JHFanDevice, entry: ConfigEntry, description: SwitchEntityDescription) -> None:
        self._device = device
        self._entry = entry
        self.entity_description = description
        self._config = _SWITCH_CONFIG[description.key]
        self._attr_unique_id = f"{DOMAIN}_{device.mac_address}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.mac_address)},
            "name": device.name, "manufacturer": "JH", "model": "Smart Fan",
        }
        self._attr_is_on = bool(device.state.get(self._config["state_key"], 0))

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_is_on = bool(self._device.state.get(self._config["state_key"], 0))
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._device.coordinator.async_config_entry_first_refresh()
        self.async_on_remove(self._device.coordinator.async_add_listener(self._handle_coordinator_update))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._config["setter"](self._device, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._config["setter"](self._device, False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"mac_address": self._device.mac_address, "dp_key": self.entity_description.key}
