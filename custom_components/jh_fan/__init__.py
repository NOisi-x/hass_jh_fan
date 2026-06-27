from __future__ import annotations
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_NAME, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from .const import DOMAIN, DEFAULT_NAME, CONF_MAX_SPEED, MAX_SPEED

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.FAN, Platform.NUMBER, Platform.SWITCH]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    from .device import JHFanDevice
    device = JHFanDevice(
        hass=hass, mac_address=entry.data[CONF_MAC],
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        max_speed=entry.data.get(CONF_MAX_SPEED, MAX_SPEED),
    )
    hass.data[DOMAIN][entry.entry_id] = device
    if not await device.async_connect():
        raise ConfigEntryNotReady("BLE connection failed, will retry")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        device = hass.data[DOMAIN].pop(entry.entry_id)
        await device.async_disconnect()
    return unload_ok

async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    if entry.entry_id in hass.data[DOMAIN]:
        device = hass.data[DOMAIN].pop(entry.entry_id)
        await device.async_disconnect()
