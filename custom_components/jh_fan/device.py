import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    WRITE_CHARACTERISTIC_UUID, NOTIFY_CHARACTERISTIC_UUID,
    DEFAULT_NAME, MAX_SPEED,
)
from .ble_protocol import JHFanProtocol

_LOGGER = logging.getLogger(__name__)

try:
    from bleak import BleakClient, BleakScanner
    from bleak_retry_connector import establish_connection
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False

PING_INTERVAL = 20
COMMAND_DEBOUNCE = 0.2
VERIFY_DELAY = 0.3
VERIFY_GAP = 0.5
SYNC_INTERVAL = 30
RECONNECT_BASE_DELAY = 2
RECONNECT_MAX_DELAY = 60


class JHFanDevice:

    def __init__(
        self, hass: HomeAssistant, mac_address: str,
        name: str = DEFAULT_NAME, max_speed: int = MAX_SPEED,
        scan_timeout: int = 10, connect_timeout: int = 30, retry_count: int = 3,
    ):
        self.hass = hass
        self.mac_address = mac_address
        self.name = name
        self.max_speed = max_speed
        self.scan_timeout = scan_timeout
        self.connect_timeout = connect_timeout
        self.retry_count = retry_count
        self.protocol = JHFanProtocol()
        self.client: Optional[BleakClient] = None
        self.connected = False
        self._update_lock = asyncio.Lock()
        self._can_control = True
        self._debounce_timer: Optional[asyncio.Task] = None
        self._last_query_time = 0.0
        self._ping_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._reconnect_attempts = 0
        self._shutting_down = False
        self._state: Dict[str, Any] = {
            "switch": 0, "angleAutoLROnOff": 0, "angleAutoUDOnOff": 0,
            "level_1": 6, "timingPowerOff1": 0, "light_1": 0,
            "mosquitoControl": 0, "voiceaAnnounce": 0,
        }
        self.coordinator = DataUpdateCoordinator(
            hass, _LOGGER, name=f"{name} Coordinator",
            update_method=self._async_update_data,
            update_interval=timedelta(seconds=SYNC_INTERVAL),
        )

    async def async_connect(self) -> bool:
        if not BLEAK_AVAILABLE:
            return False
        self._shutting_down = False
        self._reconnect_attempts = 0
        success = await self._do_connect()
        if success:
            self._start_ping()
        return success

    async def _do_connect(self) -> bool:
        try:
            scanner = BleakScanner()
            await scanner.start()
            await asyncio.sleep(2)
            devices = await scanner.discover(timeout=self.scan_timeout, return_adv=True)
            for device, adv_data in devices.values():
                if device.address.lower() == self.mac_address.lower():
                    self.client = await establish_connection(
                        BleakClient, device, self.name,
                        max_attempts=self.retry_count, timeout=self.connect_timeout,
                    )
                    self.client.set_disconnected_callback(self._on_disconnect)
                    self.connected = True
                    await self._enable_notifications()
                    await scanner.stop()
                    await self._query_device_state()
                    self._reconnect_attempts = 0
                    return True
            await scanner.stop()
        except Exception as e:
            _LOGGER.debug("Connection attempt failed: %s", e)
        self.connected = False
        self.client = None
        return False

    def _on_disconnect(self, client: BleakClient) -> None:
        self.connected = False
        self.client = None
        if not self._shutting_down:
            self.hass.loop.call_soon_threadsafe(self._schedule_reconnect)

    def _schedule_reconnect(self) -> None:
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = self.hass.async_create_task(self._auto_reconnect())

    async def _auto_reconnect(self) -> None:
        if self._shutting_down or self.connected:
            return
        self._reconnect_attempts += 1
        delay = min(RECONNECT_BASE_DELAY * (2 ** (self._reconnect_attempts - 1)), RECONNECT_MAX_DELAY)
        await asyncio.sleep(delay)
        if self._shutting_down or self.connected:
            return
        if await self._do_connect():
            self._start_ping()
            await self.coordinator.async_refresh()

    def _start_ping(self) -> None:
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
        self._ping_task = self.hass.async_create_task(self._ping_loop())

    async def _ping_loop(self) -> None:
        while self.connected and not self._shutting_down:
            await asyncio.sleep(PING_INTERVAL)
            if not self.connected or self._shutting_down:
                break
            try:
                cmd = self.protocol.build_packet(0xFF, 0)
                async with self._update_lock:
                    await self.client.write_gatt_char(WRITE_CHARACTERISTIC_UUID, cmd, response=False)
            except Exception:
                self.connected = False
                break

    def _stop_ping(self) -> None:
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            self._ping_task = None

    async def _enable_notifications(self) -> None:
        if not self.client or not self.connected:
            return
        await self.client.start_notify(NOTIFY_CHARACTERISTIC_UUID, self._notification_handler)

    async def _query_device_state(self) -> None:
        import time
        now = time.monotonic()
        if now - self._last_query_time < VERIFY_GAP:
            return
        self._last_query_time = now
        cmd = self.protocol.build_query_all_command()
        await self.send_command(cmd)

    async def async_disconnect(self) -> None:
        self._shutting_down = True
        self._stop_ping()
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            self._reconnect_task = None
        if self.client and self.connected:
            try:
                await self.client.stop_notify(NOTIFY_CHARACTERISTIC_UUID)
                await self.client.disconnect()
            except Exception as e:
                _LOGGER.debug("Disconnect error: %s", e)
        self.connected = False
        self.client = None

    def _notification_handler(self, _sender: Any, data: bytearray) -> None:
        raw = bytes(data)
        try:
            parsed = self.protocol.parse_report(raw)
        except Exception:
            return
        if not parsed:
            _LOGGER.debug("通知已忽略（无有效数据）")
            return
        state_changed = False
        for key in ("switch", "angleAutoLROnOff", "angleAutoUDOnOff",
                     "level_1", "timingPowerOff1", "light_1",
                     "mosquitoControl", "voiceaAnnounce"):
            if key in parsed and self._state.get(key) != parsed[key]:
                _LOGGER.debug("状态变化: %s %s -> %s", key, self._state.get(key), parsed[key])
                self._state[key] = parsed[key]
                state_changed = True
        if state_changed:
            self.hass.loop.call_soon_threadsafe(
                self.coordinator.async_set_updated_data, self._state.copy()
            )

    async def send_command(self, command: bytes) -> bool:
        if not self.connected or not self.client:
            return False
        try:
            async with self._update_lock:
                await self.client.write_gatt_char(WRITE_CHARACTERISTIC_UUID, command, response=False)
            return True
        except Exception:
            self.connected = False
            self.client = None
            self._schedule_reconnect()
            return False

    async def _send_dp_command(self, dp_key: str, value: int) -> bool:
        cmd = self.protocol.build_command(dp_key, value)
        if cmd is None:
            return False
        return await self.send_command(cmd)

    async def _apply_change(self, **changes: int) -> bool:
        if not self._can_control:
            return False
        self._state.update(changes)
        success = True
        for dp_key, value in changes.items():
            if not await self._send_dp_command(dp_key, value):
                success = False
        if success:
            self._can_control = False
            self.coordinator.async_set_updated_data(self._state.copy())
            self._debounce_timer = self.hass.async_create_task(self._verify_and_restore())
        return success

    async def _verify_and_restore(self) -> None:
        await asyncio.sleep(VERIFY_DELAY)
        if self.connected:
            await self._query_device_state()
        self._can_control = True

    async def set_power(self, power_on: bool) -> bool:
        return await self._apply_change(**{"switch": 1 if power_on else 0})

    async def set_speed(self, speed: int) -> bool:
        speed = max(1, min(self.max_speed, int(speed)))
        return await self._apply_change(**{"level_1": speed})

    async def set_power_and_speed(self, power_on: bool, speed: int) -> bool:
        speed = max(1, min(self.max_speed, int(speed)))
        return await self._apply_change(**{"switch": 1 if power_on else 0, "level_1": speed})

    async def set_oscillation(self, horizontal: bool, vertical: bool) -> bool:
        changes = {}
        if horizontal is not None:
            changes["angleAutoLROnOff"] = 1 if horizontal else 0
        if vertical is not None:
            changes["angleAutoUDOnOff"] = 1 if vertical else 0
        return await self._apply_change(**changes) if changes else False

    async def set_light(self, light_on: bool) -> bool:
        return await self._apply_change(**{"light_1": 1 if light_on else 0})

    async def set_timer(self, hours: int) -> bool:
        hours = max(0, min(12, int(hours)))
        return await self._apply_change(**{"timingPowerOff1": hours})

    async def set_mosquito_mode(self, mosquito_on: bool) -> bool:
        return await self._apply_change(**{"mosquitoControl": 1 if mosquito_on else 0})

    async def set_vertical_oscillation(self, on: bool) -> bool:
        return await self._apply_change(**{"angleAutoUDOnOff": 1 if on else 0})

    async def set_voice_announce(self, voice_on: bool) -> bool:
        return await self._apply_change(**{"voiceaAnnounce": 1 if voice_on else 0})

    async def _async_update_data(self) -> Dict[str, Any]:
        if not self.connected:
            raise UpdateFailed("Device not connected")
        await self._query_device_state()
        return self._state.copy()

    @property
    def state(self) -> Dict[str, Any]:
        return self._state.copy()

    @property
    def is_on(self) -> bool:
        return bool(self._state.get("switch", 0))

    @property
    def speed(self) -> int:
        return self._state.get("level_1", 6)

    @property
    def oscillation_horizontal(self) -> bool:
        return bool(self._state.get("angleAutoLROnOff", 0))

    @property
    def oscillation_vertical(self) -> bool:
        return bool(self._state.get("angleAutoUDOnOff", 0))
