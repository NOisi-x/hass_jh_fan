import logging
from typing import Optional, Dict, Any, List, Union

from .const import (
    PKT_HEADER, PKT_FOOTER, PKT_SEQ_MAX, FAN_DP_CODES,
    FAN_REPORT_KEYS, CMD_ALL, RPT_ALL, MIN_SPEED, MAX_SPEED,
)

_LOGGER = logging.getLogger(__name__)


class JHFanProtocol:

    def __init__(self):
        self._sequence = 1

    def _next_seq(self) -> int:
        seq = self._sequence
        self._sequence += 1
        if self._sequence > PKT_SEQ_MAX:
            self._sequence = 1
        return seq

    @staticmethod
    def _checksum(data: bytes) -> int:
        return sum(data) % 256

    def build_packet(self, dp_code: int, value: Union[int, List[int], bytes]) -> bytes:
        if isinstance(value, int):
            payload = bytes([value])
        elif isinstance(value, list):
            payload = bytes(value)
        elif isinstance(value, (bytes, bytearray)):
            payload = bytes(value)
        else:
            payload = b"\x00"

        data_len = 2 + len(payload)
        seq = self._next_seq()
        packet = bytearray([PKT_HEADER, data_len, seq, dp_code])
        packet.extend(payload)
        chk = self._checksum(packet[1:])
        packet.append(chk)
        packet.append(PKT_FOOTER)
        return bytes(packet)

    def build_command(self, dp_key: str, value: int) -> Optional[bytes]:
        dp_code = FAN_DP_CODES.get(dp_key)
        if dp_code is None:
            _LOGGER.error("Unknown DP key: %s", dp_key)
            return None
        return self.build_packet(dp_code, value)

    def build_query_all_command(self) -> bytes:
        return self.build_packet(CMD_ALL, 0)

    @staticmethod
    def validate_packet(data: bytes) -> bool:
        if len(data) < 6:
            return False
        return data[0] == PKT_HEADER and data[-1] == PKT_FOOTER

    def parse_report(self, data: bytes) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        if not self.validate_packet(data):
            return result

        data_len = data[1]
        dp_code = data[3]
        payload = data[4: data_len + 2]

        if dp_code in (RPT_ALL, CMD_ALL):
            for i, byte_val in enumerate(payload):
                if i < len(FAN_REPORT_KEYS) and FAN_REPORT_KEYS[i] is not None:
                    result[FAN_REPORT_KEYS[i]] = byte_val

        return result

    def create_power_command(self, power_on: bool) -> bytes:
        return self.build_command("switch", 1 if power_on else 0)

    def create_speed_command(self, speed: int) -> bytes:
        speed = max(MIN_SPEED, min(MAX_SPEED, int(speed)))
        return self.build_command("level_1", speed)

    def create_oscillation_command(self, horizontal: bool, vertical: bool) -> List[bytes]:
        commands = []
        if horizontal is not None:
            commands.append(self.build_command("angleAutoLROnOff", 1 if horizontal else 0))
        if vertical is not None:
            commands.append(self.build_command("angleAutoUDOnOff", 1 if vertical else 0))
        return [c for c in commands if c is not None]

    def create_light_command(self, light_on: bool) -> bytes:
        return self.build_command("light_1", 1 if light_on else 0)

    def create_timer_command(self, hours: int) -> bytes:
        hours = max(0, min(12, int(hours)))
        return self.build_command("timingPowerOff1", hours)

    def create_mosquito_command(self, mosquito_on: bool) -> bytes:
        return self.build_command("mosquitoControl", 1 if mosquito_on else 0)

    def create_voice_command(self, voice_on: bool) -> bytes:
        return self.build_command("voiceaAnnounce", 1 if voice_on else 0)
