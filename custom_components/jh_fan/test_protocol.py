#!/usr/bin/env python3
"""Test script for JH Fan Bluetooth protocol.

Based on mini-program reverse-engineered protocol:
Packet: [0xAA, data_len, seq, dp_code, value, checksum, 0x55]
"""

import asyncio
import sys
from datetime import datetime


def format_hex(data: bytes) -> str:
    """Format bytes as hex string with spaces."""
    return " ".join(f"{b:02X}" for b in data)


def build_packet(dp_code: int, value: int, seq: int = 1) -> bytes:
    """Build a test packet in the real protocol format.

    [0xAA, data_len(2+1=3), seq, dp_code, value, checksum, 0x55]
    checksum = sum(bytes from data_len to value) % 256
    """
    data = bytearray([0xAA, 3, seq, dp_code, value])
    chk = sum(data[1:]) % 256
    data.append(chk)
    data.append(0x55)
    return bytes(data)


def parse_packet(data: bytes, keys: list = None) -> dict:
    """Parse a packet and return DP key -> value mapping."""
    if len(data) < 6 or data[0] != 0xAA or data[-1] != 0x55:
        return {"error": "Invalid packet"}
    
    dp_code = data[3]
    data_len = data[1]
    payload = data[4 : data_len + 2]
    
    if dp_code == 0x53:  # Full attribute report
        if keys:
            result = {}
            for i, b in enumerate(payload):
                if i < len(keys) and keys[i]:
                    result[keys[i]] = b
            return result
        return {i: b for i, b in enumerate(payload)}
    
    # Single DP
    if payload:
        return {"dp_code": dp_code, "value": payload[0]}
    return {"dp_code": dp_code}


# Fan report key mapping (from const.py FAN_REPORT_KEYS)
FAN_KEYS = [
    "switch", "angleAutoLROnOff", "level_1", "clearn",
    "timingPowerOff1", "targetTemperature", "light_1",
    "saveEnergy", None, "voiceaAnnounce"
]


def test_packet_building():
    """Test building various packets using the real protocol."""
    print("=" * 50)
    print("Packet Building Test (Real 0xAA/0x55 Protocol)")
    print("=" * 50)

    tests = [
        ("Power ON", 1, 1),
        ("Power OFF", 1, 0),
        ("Speed 6", 2, 6),
        ("Speed 12", 2, 12),
        ("Light ON", 16, 1),
        ("Light OFF", 16, 0),
        ("Timer 3h", 3, 3),
        ("Mosquito ON", 32, 1),
        ("Voice ON", 8, 1),
        ("Query All", 0, 0),
        ("Ping", 255, 0),
        ("Wake Up", 254, 0),
    ]

    for name, dp_code, value in tests:
        packet = build_packet(dp_code, value)
        print(f"{name:15s}  dp=0x{dp_code:02X}({dp_code:3d}) value={value}  =>  {format_hex(packet)}")

    print()


def test_packet_parsing():
    """Test parsing various packets."""
    print("=" * 50)
    print("Packet Parsing Test")
    print("=" * 50)

    # Simulated full attribute report from device
    # dp_code=0x53, payload: [1, 0, 6, 0, 0, 25, 0, 0, 0, 1]
    # This means: switch=ON, h-osc=OFF, speed=6, timer=0, target=25C, light=OFF, energy=OFF, voice=ON
    payload = bytes([1, 0, 6, 0, 0, 25, 0, 0, 0, 1])
    report = bytearray([0xAA, 2 + len(payload), 42, 0x53])
    report.extend(payload)
    chk = sum(report[1:]) % 256
    report.append(chk)
    report.append(0x55)

    result = parse_packet(bytes(report), FAN_KEYS)
    print(f"Full report: {format_hex(bytes(report))}")
    print(f"Parsed: {result}")
    print()
    print("State interpretation:")
    for k, v in result.items():
        if k == "switch":
            print(f"  Power: {'ON' if v else 'OFF'}")
        elif k == "level_1":
            print(f"  Speed: {v}/12")
        elif k == "timingPowerOff1":
            print(f"  Timer: {v}h")
        elif k == "targetTemperature":
            print(f"  Target Temp: {v}°C")
        elif k == "light_1":
            print(f"  Light: {'ON' if v else 'OFF'}")
        elif k == "voiceaAnnounce":
            print(f"  Voice: {'ON' if v else 'OFF'}")
        elif k == "angleAutoLROnOff":
            print(f"  Oscillation: {'ON' if v else 'OFF'}")
    print()

    # Test invalid packet
    result = parse_packet(bytes([0x00, 0x00, 0x00, 0x00, 0x00]), FAN_KEYS)
    print(f"Invalid packet: {result}")


def test_protocol_module():
    """Test using the actual protocol module."""
    print("=" * 50)
    print("Protocol Module Test")
    print("=" * 50)

    try:
        sys.path.insert(0, ".")
        from const import FAN_DP_CODES, FAN_REPORT_KEYS
        from ble_protocol import JHFanProtocol
        
        p = JHFanProtocol()

        # Test command building (real DP codes from fanKey2Dp)
        tests = [
            ("Power ON", p.create_power_command(True)),
            ("Power OFF", p.create_power_command(False)),
            ("Speed 1", p.create_speed_command(1)),
            ("Speed 12", p.create_speed_command(12)),
            ("Light ON", p.create_light_command(True)),
            ("Timer 3h", p.create_timer_command(3)),
            ("Mosquito ON", p.create_mosquito_command(True)),
            ("Voice ON", p.create_voice_command(True)),
            ("Oscillation H+V", p.create_oscillation_command(True, True)),
            ("Query All", p.build_query_all_command()),
        ]

        for name, cmd in tests:
            if isinstance(cmd, list):
                for i, c in enumerate(cmd):
                    print(f"{name}[{i}]:  {format_hex(c)}")
            else:
                print(f"{name}:  {format_hex(cmd)}")

        # Test report parsing
        print()
        print("Report parsing test:")
        # Simulated full report
        payload = bytes([1, 0, 6, 0, 0, 25, 0, 0, 0, 1])
        report = bytearray([0xAA, 2 + len(payload), 42, 0x53])
        report.extend(payload)
        chk = sum(report[1:]) % 256
        report.append(chk)
        report.append(0x55)

        result = p.parse_report(bytes(report))
        print(f"  Raw: {format_hex(bytes(report))}")
        print(f"  Parsed: {result}")

        # Test temperature parsing
        print()
        print("Temperature parsing test:")
        for raw in [255, 254, 240, 200, 100, 0, 251]:
            temp = p.parse_temperature(raw)
            print(f"  Raw={raw} -> {temp}°C")

    except ImportError as e:
        print(f"  Cannot import protocol module: {e}")
    except Exception as e:
        print(f"  Error: {e}")


async def scan_and_test(mac: str = None):
    """Scan for devices or test specific MAC."""
    try:
        from bleak import BleakScanner, BleakClient
    except ImportError:
        print("bleak not installed. Install with: pip install bleak")
        return

    print("=" * 50)
    print("BLE Scan")
    print("=" * 50)

    scanner = BleakScanner()
    await scanner.start()
    await asyncio.sleep(2)

    devices = await scanner.discover(timeout=10, return_adv=True)

    print(f"Found {len(devices)} devices:")
    for device, adv in devices.values():
        name = device.name or "Unknown"
        addr = device.address
        rssi = adv.rssi if adv else "?"
        # Check for JH Fan service UUID
        jh_marker = ""
        if adv and adv.service_uuids:
            uuids = [str(u) for u in adv.service_uuids]
            if "0000ffb0-0000-1000-8000-00805f9b34fb" in [u.lower() for u in uuids]:
                jh_marker = " [JH FAN!]"
        print(f"  {name} ({addr}) RSSI={rssi}{jh_marker}")

    await scanner.stop()

    if mac:
        print(f"\nConnecting to {mac}...")
        try:
            async with BleakClient(mac, timeout=30) as client:
                print(f"Connected: {client.is_connected}")

                for svc in client.services:
                    print(f"  Service: {svc.uuid}")
                    for ch in svc.characteristics:
                        props = ch.properties
                        flags = []
                        if "read" in props:
                            flags.append("R")
                        if "write" in props:
                            flags.append("W")
                        if "notify" in props:
                            flags.append("N")
                        if "write-without-response" in props:
                            flags.append("Ww")
                        print(f"    Char: {ch.uuid} [{','.join(flags)}]")

        except Exception as e:
            print(f"Connection error: {e}")


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="JH Fan Protocol Test")
    parser.add_argument("--mac", help="MAC address to test")
    parser.add_argument("--protocol-only", action="store_true",
                       help="Only test protocol, no BLE scan")
    args = parser.parse_args()

    test_packet_building()
    test_packet_parsing()
    test_protocol_module()

    if not args.protocol_only:
        asyncio.run(scan_and_test(args.mac))


if __name__ == "__main__":
    main()
