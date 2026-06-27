# JH Fan — Home Assistant Integration

Bluetooth integration for JH Voice smart fans, reverse-engineered from the official mini-program using generative AI. Compatible with fans controlled by the JH Voice mini-program.

Verified device: AUX Air Circulation Fan Voice Edition (FX-L36AR-V)

## Features

| Entity | Type | DP Key | Description |
|:-------|------|--------|-------------|
| Fan | `fan` | switch / level_1 | Power, speed, horizontal oscillation |
| Ambient Light | `switch` | light_1 | Toggle ambient light |
| Mosquito Mode | `switch` | mosquitoControl | Mosquito repellent |
| Voice Announce | `switch` | voiceaAnnounce | Toggle voice announcements |
| Vertical Oscillation | `switch` | angleAutoUDOnOff | Up/down oscillation |
| Turn Off Timer | `number` | timingPowerOff1 | 0–12 hour countdown |

**Configurable max speed** — during setup, select the correct max speed for your device so percentage mapping works correctly: 3 / 6 / 8 / 12 / 32 / 36 (default 8).

## Requirements

Home Assistant with Bluetooth hardware support (ESP32 Bluetooth proxy recommended).

## Installation

### HACS

1. Open HACS → **Integrations**
2. Click **⋮** → **Custom repositories**
3. Enter repository URL, type **Integration**
4. Search **JH Fan** → **Download**
5. Restart Home Assistant

## Setup

**Settings → Add Integration → JH Fan** → choose:

1. **Scan for devices** — BLE scan, pick from list
2. **Bluetooth auto-discovery** — HA passive detection, confirm popup
3. **Manual MAC entry** — enter address directly

After device selection, choose the max speed that matches your model.

## Multi-Device

Each fan is added as a separate config entry. All entities are scoped per MAC address — no conflicts.

## Protocol

```
Packet:  [0xAA][len][seq][dp_code][data...][crc][0x55]
UUIDs:   Service  0000FFB0-0000-1000-8000-00805F9B34FB
         Write    0000FFB1
         Notify   0000FFB2
```

## State Sync

| Phase | Timing | Mechanism |
|:------|--------|-----------|
| Initial fetch | On connect | query-all |
| Optimistic update | 0ms | Local cache → instant UI |
| Delayed verify | ~0.5s | query-all → authoritative |
| Periodic sync | 30s | Full state query |
| Keep-alive ping | 20s | Prevents BLE timeout |

## Troubleshooting

| Symptom | Solution |
|:--------|----------|
| Device not found | Power on, check BLE range |
| Disconnects | Reduce distance, check ESP32 signal |
| Wrong speed range | Re-add device, select correct max speed |
| State stale | Auto-syncs every 30s |

## License

MIT
