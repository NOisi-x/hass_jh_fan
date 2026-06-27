# JH Fan 代码逻辑总结

## 文件结构

```
custom_components/jh_fan/
├── const.py          常量与 DP 码映射
├── ble_protocol.py   BLE 帧组包/解包
├── device.py         BLE 连接、状态缓存、心跳保活
├── fan.py            风扇实体（开关、调速、摇头）
├── switch.py         4 个开关实体（灯、驱蚊、语音、上下摇头）
├── number.py         1 个数字实体（定时关机）
├── config_flow.py    配置向导（BLE 扫描 + 蓝牙发现 + 手动）
├── __init__.py       入口，多设备管理
├── manifest.json     集成元数据
├── strings.json      向导 UI 文本
└── translations/     中英文翻译
```

## 数据流

```
用户操作 → entity (fan/switch/number) → device.set_xxx()
  → _apply_change(k=v) → _state.update(k=v) [乐观更新]
  → _send_dp_command(k, v) → build_command → build_packet
  → BLE write → 设备执行命令
  → _verify_and_restore() [0.5s 后 query-all 验证]
  
设备通知 → _notification_handler → parse_report(data)
  → _state.update(parsed) → async_set_updated_data → entity 刷新
```

## BLE 协议

帧格式: `[0xAA][data_len][seq][dp_code][payload...][checksum][0x55]`

- `data_len` = 2 + payload 长度
- `checksum` = data[1..payload_end] 之和 % 256
- `dp_code` = DP 功能码（来自 FAN_DP_CODES）
- 上报: `dp_code=0x53`，payload 每字节按 FAN_REPORT_KEYS 位置映射

## DP 码映射

| 功能 | DP Key | Code |
|------|--------|------|
| 电源 | switch | 1 |
| 风速 | level_1 | 2 |
| 定时 | timingPowerOff1 | 3 |
| 左右摇头 | angleAutoLROnOff | 4 |
| 上下摇头 | angleAutoUDOnOff | 5 |
| 语音 | voiceaAnnounce | 8 |
| 氛围灯 | light_1 | 16 |
| 驱蚊 | mosquitoControl | 32 |

## 上报字节映射 (FAN_REPORT_KEYS)

| 字节 | 键名 | 含义 |
|------|------|------|
| 0 | switch | 电源 |
| 1 | angleAutoLROnOff | 左右摇头 |
| 2 | level_1 | 风速 |
| 3 | clearn | 保留 |
| 4 | timingPowerOff1 | 定时 |
| 5 | targetTemperature | 目标温度 |
| 6 | light_1 | 灯光 |
| 7 | saveEnergy | 节能 |
| 8 | None | 跳过 |
| 9 | voiceaAnnounce | 语音 |

## 状态同步

| 阶段 | 时机 | 机制 |
|------|------|------|
| 初始 | 连接时 | query-all |
| 乐观 | 操作时 0ms | `_state.update()` 即时反馈 |
| 验证 | 操作后 0.5s | query-all 确认 |
| 定期 | 30s | _async_update_data 轮询 |
| 心跳 | 20s | ping 保活 |

## 命令控制链

```
fan.async_turn_on()
  → device.set_power(True)
    → _apply_change(switch=1)
      → _state["switch"] = 1      [乐观]
      → _send_dp_command("switch", 1)
        → build_command("switch", 1)
          → FAN_DP_CODES["switch"] = 1
          → build_packet(1, 1)
            → [0xAA, 3, seq, 1, 1, chk, 0x55]
      → _verify_and_restore()      [0.5s 后验证]
```

## 通知处理链

```
BLE 回调: _notification_handler(data)
  → parse_report(raw bytes)
    → validate: header=0xAA, footer=0x55
    → dp_code=0x53: 逐字节映射到 FAN_REPORT_KEYS
    → 返回 {"switch": 1, "level_1": 6, ...}
  → _state.update(parsed) [仅覆盖上报中存在的键]
  → async_set_updated_data → coordinator → entities
```

## 实体总览

| 类型 | 数量 | 来源 |
|------|------|------|
| fan | 1 | fan.py |
| switch | 4 | switch.py (灯、驱蚊、语音、上下摇头) |
| number | 1 | number.py (定时关机) |

## 配置流程

```
async_step_user         入口: 扫描 / 手动
  ├─ async_step_discovery    扫描结果列表 → 选择设备
  ├─ async_step_manual       输入 MAC + 名称
  └─ async_step_bluetooth    HA 蓝牙被动发现 → 确认
       └─ async_step_bluetooth_confirm
  └─ async_step_configure    选择最大档位 (3/6/8/12/32/36)
       └─ async_create_entry  完成
```

## 多设备

- `hass.data[DOMAIN][entry_id]` = device
- 实体 unique_id = `{DOMAIN}_{MAC}_{key}`
- 实体 device_info 按 MAC 分组
- async_unload_entry 按 entry_id 断开

## 保活与重连

- ping: 20s 间隔发送 dp_code=255
- 断开检测: BleakClient.set_disconnected_callback
- 重连: 指数退避 (2s → 4s → 8s → ... → 60s)
