from __future__ import annotations
import logging
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from .const import DOMAIN, DEFAULT_NAME, SERVICE_UUID, CONF_MAX_SPEED, MAX_SPEED

_LOGGER = logging.getLogger(__name__)
SCAN_TIMEOUT = 10

def _format_mac(raw: str) -> str | None:
    mac = raw.upper().replace(":", "").replace("-", "").replace(" ", "").strip()
    if len(mac) != 12:
        return None
    try:
        int(mac, 16)
        return ":".join(mac[i : i + 2] for i in range(0, 12, 2))
    except ValueError:
        return None

class JHConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._discovered: list[dict[str, str]] = []
        self._pending_address: str = ""
        self._pending_name: str = ""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if not self._discovered:
            self._discovered = await self._scan_for_devices()
        if user_input is not None:
            if user_input.get("action") == "scan":
                return await self.async_step_discovery()
            if user_input.get("action") == "manual":
                return await self.async_step_manual()
            if user_input.get("action") == "pick":
                selected = user_input.get("device")
                for dev in self._discovered:
                    if dev["address"] == selected:
                        self._pending_address = dev["address"]
                        self._pending_name = dev["name"]
                        return await self.async_step_configure()
        if len(self._discovered) > 0:
            devices = {dev["address"]: f"{dev['name']} ({dev['address']})" for dev in self._discovered}
            schema = vol.Schema({
                vol.Required("action"): vol.In({"pick": "从列表选择", "scan": "重新扫描", "manual": "手动输入 MAC 地址"}),
                vol.Required("device"): vol.In(devices),
            })
        else:
            schema = vol.Schema({
                vol.Required("action"): vol.In({"scan": "扫描附近设备", "manual": "手动输入 MAC 地址"}),
            })
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_discovery(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            selected = user_input.get("device")
            for dev in self._discovered:
                if dev["address"] == selected:
                    self._pending_address = dev["address"]
                    self._pending_name = dev["name"]
                    return await self.async_step_configure()
            return await self.async_step_manual()
        devices = {dev["address"]: f"{dev['name']} ({dev['address']})" for dev in self._discovered}
        return self.async_show_form(
            step_id="discovery",
            data_schema=vol.Schema({vol.Required("device"): vol.In(devices)}),
            description_placeholders={"count": str(len(self._discovered))},
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            formatted = _format_mac(user_input[CONF_MAC])
            if formatted is None:
                errors[CONF_MAC] = "invalid_mac"
            else:
                await self.async_set_unique_id(formatted)
                self._abort_if_unique_id_configured()
                self._pending_address = formatted
                self._pending_name = user_input.get(CONF_NAME, DEFAULT_NAME)
                return await self.async_step_configure()
        return self.async_show_form(step_id="manual", data_schema=vol.Schema({
            vol.Required(CONF_MAC): str, vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        }), errors=errors)

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> FlowResult:
        address = discovery_info.address
        name = discovery_info.name or f"JH Fan ({address[:8]})"
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        self._discovered = [{"address": address, "name": name}]
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            dev = self._discovered[0]
            self._pending_address = dev["address"]
            self._pending_name = dev["name"]
            return await self.async_step_configure()
        dev = self._discovered[0]
        return self.async_show_form(step_id="bluetooth_confirm", description_placeholders={"name": dev["name"], "address": dev["address"]})

    async def async_step_configure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title=self._pending_name, data={
                CONF_MAC: self._pending_address, CONF_NAME: self._pending_name,
                CONF_MAX_SPEED: user_input.get(CONF_MAX_SPEED, MAX_SPEED),
            })
        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema({
                vol.Required(CONF_MAX_SPEED, default=MAX_SPEED): vol.In([3, 6, 8, 12, 32, 36]),
            }),
            description_placeholders={
                "name": self._pending_name,
                "address": self._pending_address,
            },
        )

    async def _scan_for_devices(self) -> list[dict[str, str]]:
        try:
            from bleak import BleakScanner
        except ImportError:
            return []
        devices = []
        try:
            scanner = BleakScanner()
            results = await scanner.discover(timeout=SCAN_TIMEOUT, return_adv=True)
            for device, adv_data in results.values():
                name = device.name or device.address
                addr = device.address
                if adv_data and adv_data.service_uuids:
                    uuids = [str(u).lower() for u in adv_data.service_uuids]
                    if SERVICE_UUID.lower() in uuids:
                        devices.append({"address": addr, "name": name})
                        continue
                name_upper = name.upper()
                if any(tag in name_upper for tag in ("JH", "FAN", "JIANHUI")):
                    devices.append({"address": addr, "name": name})
        except Exception:
            pass
        return devices
