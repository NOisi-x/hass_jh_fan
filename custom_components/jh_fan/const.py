DOMAIN = "jh_fan"
DEFAULT_NAME = "JH Fan"
CONF_MAX_SPEED = "max_speed"
SERVICE_UUID = "0000FFB0-0000-1000-8000-00805F9B34FB"
WRITE_CHARACTERISTIC_UUID = "0000FFB1-0000-1000-8000-00805F9B34FB"
NOTIFY_CHARACTERISTIC_UUID = "0000FFB2-0000-1000-8000-00805F9B34FB"
PKT_HEADER = 0xAA
PKT_FOOTER = 0x55
PKT_SEQ_MAX = 254
CMD_ALL = 0
CMD_PING = 255
CMD_WAKEUP = 254
CMD_UNBIND = 250
CMD_SYNC_TIME = 249
CMD_CLOSE_CUSTOM_VOICE = 248
CMD_SPEECH_LEN = 128
CMD_SPEECH_DATA = 129
CMD_SPEECH_RESET = 141
CMD_CONTENT = 153
CMD_GRAMMAR = 154
RPT_ALL = 0x53
FAN_DP_CODES = {
    "switch": 1, "level_1": 2, "timingPowerOff1": 3,
    "angleAutoLROnOff": 4, "angleAutoUDOnOff": 5, "anionOnOff": 6,
    "mode_5": 7, "voiceaAnnounce": 8, "purify": 9, "sleepMode": 10,
    "saveEnergy": 11, "voiceControl": 12, "humidificationSwitch": 13,
    "screenOnOff": 14, "timingPowerOn": 15, "light_1": 16, "cool": 17,
    "brightnessChange": 18, "angleValue": 19, "humanSensor": 20,
    "screenBrightness": 21, "light_2": 22, "level_2": 23,
    "timingPowerOff3": 24, "timingPowerOff2": 25, "lock": 26,
    "naturalWind": 27, "IonPurification": 28, "UVPurification": 29,
    "UvDisinfect": 30, "volumeAdjust": 31, "mosquitoControl": 32,
    "smartWind": 33, "nightLight": 34, "atomization": 35,
    "temperatureShow": 36, "fanStorm": 37, "babyMode": 38,
    "upDownAirSupplyAngle": 39, "adjustAngle": 40, "mute": 41,
    "angleOnOff": 42, "drying": 43, "refrigeration": 44,
    "lowHeating": 45, "highHeating": 46, "seaBreezeMode": 47,
    "targetTemperature": 48, "airConditionerMode": 49, "childMode": 50,
    "airConditionerFanLevel": 51,
}
FAN_REPORT_KEYS = [
    "switch", "angleAutoLROnOff", None, "level_1",
    "timingPowerOff1", "targetTemperature", "light_1", "saveEnergy",
    None, "voiceaAnnounce",
]
MIN_SPEED = 1
MAX_SPEED = 8
DEFAULT_SPEED = 6
