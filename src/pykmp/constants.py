# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

"""Constants/definitions for the Kamstrup KMP protocol."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping  # pragma: no cover
    from typing import Final  # pragma: no cover


# Decimals of each variable in the GetRegister command request/response (CID=0x10)
REGISTERS: Final[Mapping[int, str]] = {
    60: "Heat Energy (E1)",
    61: "Inlet Energy E4",
    62: "Outlet Energy E5",
    63: "Cooling Energy E3",
    64: "Tariff TA2",
    65: "Tariff TA3",
    66: "Tariff limit 2",
    67: "Tariff limit 3",
    68: "Volume V1",
    69: "Volume V2",
    72: "Mass M1",
    73: "Mass M2",
    74: "Flow V1",
    75: "Flow V2",
    80: "Current Power",
    84: "Pulse input A1",
    85: "Pulse input B1",
    86: "Temp1",
    87: "Temp2",
    88: "Temp3",
    89: "Tempdiff",
    91: "Pressure P1",
    92: "Pressure P1",
    94: "Heat Energy E2",
    95: "Tap water energy E6",
    96: "Tap water energy E7",
    97: "Temp1xm3 E8", # V1 * t1 (inlet)
    98: "Target Date",
    99: "InfoCode",
    104: "Meter number for VB",
    110: "Temp2xm3 E9", # V2 * t2 (outlet)
    112: "Customer Number 2", # 8 most-significant digits
    113: "Infoevent",
    114: "Meter number for VA",
    122: "Temp4",
    123: "MaxFlowDate_Y",
    124: "MaxFlow_Y",
    125: "MinFlowDate_Y",
    126: "MinFlow_Y",
    127: "MaxPowerDate_Y",
    128: "MaxPower_Y",
    129: "MinPowerDate_Y",
    130: "MinPower_Y",
    138: "MaxFlowDate_M",
    139: "MaxFlow_M",
    140: "MinFlowDate_M",
    141: "MinFlow_M",
    142: "MaxPowerDate_M",
    143: "MaxPower_M",
    144: "MinPowerDate_M",
    145: "MinPower_M",
    146: "AvgTemp1_Y",
    147: "AvgTemp2_Y",
    149: "AvgTemp1_M",
    150: "AvgTemp2_M",
    152: "Program number", # not seen on my meters: ABCCCCCC
    153: "Config number 1", # config no. DDDEE
    154: "Software Checksum 1",
    168: "Config number 2", # config no. FFGGMN
    175: "Error hour counter",
    178: "Differential energy dE",
    179: "Control energy cE",
    180: "Differential volume dV",
    181: "Control volume cV",
    # 183: looks like a meter S/N on our Multical 603
    184: "MbusPriAdrMod1",
    185: "MbusSekAdrMod1",
    218: "MbusPriAdrMod2",
    219: "MbusSekAdrMod2",
    222: "ConfigChangedEventCount",
    224: "Pulse input A2",
    225: "Pulse input B2",
    229: "T1_average_autoint",
    230: "T2_average_autoint",
    234: "l/imp. for VA",
    235: "l/imp for VB",
    239: "Volume V1 hires",
    # Undocumented, but it matches the info given by our Multical 603 in the diagnostics display
    259: "Nominal Q\N{LATIN SUBSCRIPT SMALL LETTER P}",
    266: "E1HighRes",
    267: "Cooling energy E3 hires",
    346: "Module SW rev",
    347: "Customer Number",
    348: "Date and Time", # FIXME unkown unit 79, 28591984415535
    355: "COP Year",
    362: "Tariff TA4",
    364: "Heat energy A1", # Heat energy with discount A1, t2 < t5 limit
    365: "Heat energy A2", # Heat energy with surcharge A2, t2 > t5 limit
    366: "T5 limit",
    367: "COP Month",
    369: "Info bits",
    371: "COP",
    372: "Power Input B1",
    379: "T1 time average day",
    380: "T2 time average day",
    381: "T1 time average hour",
    382: "T2 time average hour",
    383: "Flow V1 max year date",
    # 384: something similar?
    385: "Power max year date",
    # 386: something similar?
    387: "Flow V1 max month date",
    # 388: something similar?
    389: "Power max month date",
    # 390: something similar?
    398: "T1 actual (one decimal)",
    399: "T2 actual (one decimal)",
    # Undocumented, but on Multical 603 it works that way
    400: "T1-T2 (one decimal)",
    404: "Meter Type",
    473: "Energy E10",
    474: "Energy E11",
    477: "T3 time average day",
    478: "T3 time average hour",
    505: "P1 average day",
    506: "P2 average day",
    507: "P1 average hour",
    508: "P2 average hour",
    # Undocumented, but it matches the actual interval on Multical 303
    675: "WM-Bus transmission interval",
    1001: "Fabrication No",
    1002: "Time",
    1003: "Date",
    1004: "HourCounter",
    1005: "Software edition",
    1010: "Customer number 1", # 8 least-significant digits
    1032: "Operation Mode",
}


UNITS_NAMES: Final[Mapping[int, str]] = {
    0x00: "no unit (number)",
    0x01: "Wh",
    0x02: "kWh",
    0x03: "MWh",
    0x04: "GWh",
    0x05: "J",
    0x06: "kJ",
    0x07: "MJ",
    0x08: "GJ",
    0x09: "Cal",
    0x0A: "kCal",
    0x0B: "Mcal",
    0x0C: "Gcal",
    0x0D: "varh",
    0x0E: "kvarh",
    0x0F: "Mvarh",
    0x10: "Gvarh",
    0x11: "VAh",
    0x12: "kVAh",
    0x13: "MVAh",
    0x14: "GVAh",
    0x15: "W",
    0x16: "kW",
    0x17: "MW",
    0x18: "GW",
    0x19: "var",
    0x1A: "kvar",
    0x1B: "Mvar",
    0x1C: "Gvar",
    0x1D: "VA",
    0x1E: "kVA",
    0x1F: "MVA",
    0x20: "GVA",
    0x21: "V",
    0x22: "A",
    0x23: "kV",
    0x24: "kA",
    0x25: "°C",
    0x26: "K",
    0x27: "l",
    0x28: "m³",
    0x29: "l/h",
    0x2A: "m³/h",
    0x2B: "m³\N{MULTIPLICATION SIGN}C",
    0x2C: "ton",
    0x2D: "ton/h",
    0x2E: "h",
    0x2F: "hh:mm:ss",
    0x30: "yy:mm:dd",
    0x31: "yyyy:mm:dd",
    0x32: "mm:dd",
    0x33: "no unit (number)",
    0x34: "bar",
    0x35: "RTC",
    0x36: "ASCII",
    0x37: "m³ \N{MULTIPLICATION SIGN}10",
    0x38: "ton \N{MULTIPLICATION SIGN}10",
    0x39: "GJ \N{MULTIPLICATION SIGN}10",
    0x3A: "minutes",
    0x3B: "Bitfield",
    0x3C: "s",
    0x3D: "ms",
    0x3E: "days",
    0x3F: "RTC-Q",
    0x40: "Datetime",
    0x4f: "DST YY-MM-DD hh:mm:ss",
    0x55: "%RH",
    0x56: "%O\N{SUBSCRIPT TWO}",
    0x57: "m/s",
    0x58: "kJ/kg",
    0x59: "pH",
    0x5A: "g/kg",
}


@enum.unique
class ByteCode(enum.Enum):
    """Special byte values on the physical layer."""

    START_FROM_METER = 0x40
    START_TO_METER = 0x80
    STOP = 0x0D
    ACK = 0x06
    STUFFING = 0x1B


@enum.unique
class DestinationAddress(enum.Enum):
    """Data link layer address."""

    HEAT_METER = 0x3F
    LOGGER_TOP = 0x7F
    LOGGER_BASE = 0xBF


ACK_BYTES: Final[bytes] = ByteCode.ACK.value.to_bytes(1, "big")


@enum.unique
class CommandId(enum.Enum):
    """CID values for messages."""

    GET_TYPE = 0x01
    GET_SERIAL = 0x02
    SET_CLOCK = 0x09
    GET_REGISTER = 0x10
    PUT_REGISTER = 0x11
    GET_EVENT_STATUS = 0x9B
    CLEAR_EVENT_STATUS = 0x9C
    GET_LOG_TIME_PRESENT = 0xA0
    GET_LOG_PAST_PRESENT = 0xA1
    GET_LOG_ID_PRESENT = 0xA2
    GET_LOG_TIME_PAST = 0xA3
    LOGGER = 0xb8


@enum.unique
class LoggerSubCommandId(enum.Enum):
    """Logger sub-commands"""
    GET_CONFIGURATION = 0x05
    GET_LOG_ID_PAST_ABS = 0x06
    GET_LOG_LAST_ENTRY_PAST_ABS = 0x07
    GET_LOG_ID = 0x08
    GET_LOG_NEXT_FORMAT = 0x09


@enum.unique
class LoggerType(enum.Enum):
    """Types of loggers"""
    CONFIG = 0
    INFO = 1
    INTERVAL_YEAR = 2
    INTERVAL_MONTH = 3
    INTERVAL_DAY = 4
    INTERVAL_HOUR = 5
    INTERVAL_MIN1 = 6
    INTERVAL_MIN2 = 7
    SW_DOWNLOAD_SUCCESS = 8
    SW_DOWNLOAD_AUDIT = 9

class LoggerInfo(enum.Flag):
    """Special situation of a log output"""
    NO_LOG_ENTRIES = 1 << 0
    OUT_OF_RANGE = 1 << 1
    RESERVED_BIT2 = 1 << 1
    UNSUPPORTED_REGISTER = 1 << 3
    TRUNCATED_ENTRIES = 1 << 4
    FORMAT_CHANGED = 1 << 5
    TAIL_INCLUDED = 1 << 6
    HEAD_INCLUDED = 1 << 7
    MEMORY_ERROR = 1 << 8
    INVALID_REQUEST = 1 << 9
    RESERVED_BIT10 = 1 << 10
    RESERVED_BIT11 = 1 << 11
    RESERVED_BIT12 = 1 << 12
    TRUNCATED_REGISTERS = 1 << 13
    RESERVED_BIT14 = 1 << 14
    RESERVED_BIT15 = 1 << 15
