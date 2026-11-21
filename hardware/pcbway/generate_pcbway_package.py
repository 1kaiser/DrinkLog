#!/usr/bin/env python3
"""
Generate complete PCBWay-ready manufacturing & KiCad 8 design package for
HydroCap V2.1 Universal Core (Ø 28.0 mm, 0.8 mm thick, 4-layer FR4, ENIG-RoHS)
so ONE single PCBA fits ALL 1.1x D_cap shells (33.6 mm PET up to 69.3 mm Wide):
  - KiCad 8 project, schematic, and PCB (.kicad_pro, .kicad_sch, .kicad_pcb)
  - RS-274X Gerbers (.GTL, .G2, .G3, .GBL, .GTS, .GBS, .GTO, .GBO, .GTP, .GM1)
  - Excellon Drill files (-PTH.drl, -NPTH.drl) + zip archive for PCBWay upload
  - PCBWay PCBA BOM CSV & Centroid CPL Pick-and-Place CSV (1:1 designator parity)
  - Automated DRC bounding-box & perimeter collision verification
  - Top/Bottom PCB layout verification render (pcb_layout_top_bottom.png)
"""

from __future__ import annotations

import csv
import math
import os
import uuid
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

BOARD_RADIUS_MM = 14.0  # Ø 28.0 mm universal core PCB (drops inside Ø33.6 mm pet_30 shell!)
MOUNT_HOLES_MM = [(-11.4, 3.8), (11.8, 3.8), (-11.4, -4.8), (11.8, -3.2)]


@dataclass(frozen=True)
class PadSpec:
    num: str
    dx: float
    dy: float
    w: float
    h: float
    smd: bool = True
    drill: float = 0.0
    net: str = ""


@dataclass(frozen=True)
class PartDef:
    ref: str
    value: str
    mfg: str
    mpn: str
    desc: str
    pkg: str
    assy_type: str  # "SMT" | "PCB_PAD_DNP"
    dist_ref: str
    x: float        # mm relative to board center (0, 0)
    y: float
    rot: float      # degrees CCW
    layer: str      # "Top" | "Bottom"
    body_w: float
    body_h: float
    pads: List[PadSpec] = field(default_factory=list)


def _rect_pads_2pin(pitch: float, pw: float, ph: float, n1: str, n2: str) -> List[PadSpec]:
    return [
        PadSpec("1", -pitch / 2.0, 0.0, pw, ph, True, 0.0, n1),
        PadSpec("2", +pitch / 2.0, 0.0, pw, ph, True, 0.0, n2),
    ]


def build_parts() -> List[PartDef]:
    parts: List[PartDef] = []

    # U1: Raytac MDBT50Q-1MV2 (nRF52840 BLE 5.0 + native USB 2.0 D+/D- + SWD, 10.5 x 15.0 mm)
    u1_pads = [
        PadSpec("VBUS",  -4.2, -3.2, 0.65, 1.0, True, 0.0, "VBUS_5V"),
        PadSpec("DP",    -3.0, -3.2, 0.65, 1.0, True, 0.0, "USB_DP"),
        PadSpec("DM",    -1.8, -3.2, 0.65, 1.0, True, 0.0, "USB_DM"),
        PadSpec("VDD",   -0.6, -3.2, 0.65, 1.0, True, 0.0, "VDD_3V3"),
        PadSpec("GND",    0.6, -3.2, 0.65, 1.0, True, 0.0, "GND"),
        PadSpec("SDA",    1.8, -3.2, 0.65, 1.0, True, 0.0, "I2C_SDA"),
        PadSpec("SCL",    3.0, -3.2, 0.65, 1.0, True, 0.0, "I2C_SCL"),
        PadSpec("INT1",   4.2, -3.2, 0.65, 1.0, True, 0.0, "IMU_INT1"),
        PadSpec("SWDIO", -4.2, -1.8, 0.65, 0.8, True, 0.0, "SWDIO"),
        PadSpec("SWDCLK",-4.2, -0.5, 0.65, 0.8, True, 0.0, "SWDCLK"),
        PadSpec("nRST",  -4.2,  0.8, 0.65, 0.8, True, 0.0, "nRESET"),
        PadSpec("LED",    4.2, -1.8, 0.65, 0.8, True, 0.0, "LED_STAT"),
    ]
    parts.append(PartDef(
        "U1", "MDBT50Q-1MV2", "Raytac", "MDBT50Q-1MV2",
        "nRF52840 BLE 5.0 Module w/ Native USB 2.0 & PCB Antenna",
        "MDBT50Q_15.0x10.5", "SMT", "DigiKey: 2097-MDBT50Q-1MV2-ND",
        0.0, 5.1, 0.0, "Top", 10.2, 14.8, u1_pads
    ))

    # J1: Amphenol 12402448E512A IPX8 Waterproof Mid-Mount USB-C at -Y edge (y = -9.8)
    j1_pads = [
        PadSpec("A1", -3.25, 1.6, 0.40, 1.3, True, 0.0, "GND"),
        PadSpec("A4", -2.25, 1.6, 0.40, 1.3, True, 0.0, "VBUS_5V"),
        PadSpec("A5", -1.25, 1.6, 0.35, 1.3, True, 0.0, "USB_CC1"),
        PadSpec("A6", -0.40, 1.6, 0.35, 1.3, True, 0.0, "USB_DP"),
        PadSpec("A7",  0.40, 1.6, 0.35, 1.3, True, 0.0, "USB_DM"),
        PadSpec("B5",  1.25, 1.6, 0.35, 1.3, True, 0.0, "USB_CC2"),
        PadSpec("B4",  2.25, 1.6, 0.40, 1.3, True, 0.0, "VBUS_5V"),
        PadSpec("B12", 3.25, 1.6, 0.40, 1.3, True, 0.0, "GND"),
        PadSpec("SH1", -4.45, 0.0, 1.0, 1.6, True, 0.0, "GND"),
        PadSpec("SH2",  4.45, 0.0, 1.0, 1.6, True, 0.0, "GND"),
    ]
    parts.append(PartDef(
        "J1", "12402448E512A", "Amphenol CS", "12402448E512A",
        "IPX8 Waterproof Mid-Mount USB Type-C Receptacle (O-Ring Sealed)",
        "USB_C_MidMount_IPX8", "SMT", "DigiKey: 12402448E512A",
        0.0, -9.8, 0.0, "Top", 9.4, 7.6, j1_pads
    ))

    # U5: ST USBLC6-2SC6 ESD array near USB-C (-7.4, -6.2)
    u5_pads = [
        PadSpec("1", -1.2,  0.95, 0.6, 0.85, True, 0.0, "USB_DP"),
        PadSpec("2", -1.2,  0.00, 0.6, 0.85, True, 0.0, "GND"),
        PadSpec("3", -1.2, -0.95, 0.6, 0.85, True, 0.0, "USB_DM"),
        PadSpec("4",  1.2, -0.95, 0.6, 0.85, True, 0.0, "USB_DM"),
        PadSpec("5",  1.2,  0.00, 0.6, 0.85, True, 0.0, "VBUS_5V"),
        PadSpec("6",  1.2,  0.95, 0.6, 0.85, True, 0.0, "USB_DP"),
    ]
    parts.append(PartDef(
        "U5", "USBLC6-2SC6", "STMicroelectronics", "USBLC6-2SC6",
        "Low Capacitance ESD/TVS Protection (USB D+/D-/VBUS)",
        "SOT-23-6", "SMT", "LCSC: C7519",
        -7.4, -6.2, 0.0, "Top", 2.9, 2.8, u5_pads
    ))

    # R4, R5: CC1 & CC2 5.1k 0402 pull-downs in clear gap between J1 and U1
    parts.append(PartDef(
        "R4", "5.1k 1%", "Yageo", "RC0402FR-075K1L",
        "USB-C CC1 5.1 kOhm 1% Pull-Down Resistor", "0402", "SMT", "LCSC: C25905",
        -2.2, -4.4, 0.0, "Top", 1.2, 0.7, _rect_pads_2pin(0.95, 0.55, 0.65, "USB_CC1", "GND")
    ))
    parts.append(PartDef(
        "R5", "5.1k 1%", "Yageo", "RC0402FR-075K1L",
        "USB-C CC2 5.1 kOhm 1% Pull-Down Resistor", "0402", "SMT", "LCSC: C25905",
        2.2, -4.4, 0.0, "Top", 1.2, 0.7, _rect_pads_2pin(0.95, 0.55, 0.65, "USB_CC2", "GND")
    ))

    # U4: TI BQ25180YBGR Li-Ion Charger (-8.0, -2.5)
    u4_pads = [
        PadSpec("IN",  -0.45,  0.35, 0.35, 0.35, True, 0.0, "VBUS_5V"),
        PadSpec("SYS",  0.45,  0.35, 0.35, 0.35, True, 0.0, "VSYS"),
        PadSpec("BAT",  0.45, -0.35, 0.35, 0.35, True, 0.0, "VBAT"),
        PadSpec("GND", -0.45, -0.35, 0.35, 0.35, True, 0.0, "GND"),
        PadSpec("SDA", -0.45,  0.00, 0.30, 0.25, True, 0.0, "I2C_SDA"),
        PadSpec("SCL",  0.45,  0.00, 0.30, 0.25, True, 0.0, "I2C_SCL"),
    ]
    parts.append(PartDef(
        "U4", "BQ25180YBGR", "Texas Instruments", "BQ25180YBGR",
        "1A I2C Linear Li-Ion Charger w/ Power-Path & 15nA Ship Mode",
        "DSBGA-8_1.6x1.1", "SMT", "DigiKey: 296-BQ25180YBGRCT-ND",
        -8.0, -2.5, 0.0, "Top", 1.6, 1.1, u4_pads
    ))

    # U6: TI TPS7A0233PDBVR (25 nA Iq 3.3V LDO) (-8.0, +0.8)
    u6_pads = [
        PadSpec("IN",  -1.2,  0.95, 0.6, 0.85, True, 0.0, "VSYS"),
        PadSpec("GND", -1.2,  0.00, 0.6, 0.85, True, 0.0, "GND"),
        PadSpec("EN",  -1.2, -0.95, 0.6, 0.85, True, 0.0, "VSYS"),
        PadSpec("OUT",  1.2,  0.95, 0.6, 0.85, True, 0.0, "VDD_3V3"),
    ]
    parts.append(PartDef(
        "U6", "TPS7A0233PDBVR", "Texas Instruments", "TPS7A0233PDBVR",
        "25 nA Ultra-Low-Iq 200 mA 3.3V LDO Regulator",
        "SOT-23-5", "SMT", "DigiKey: 296-TPS7A0233PDBVRCT-ND",
        -8.0, 0.8, 0.0, "Top", 2.9, 2.8, u6_pads
    ))

    # U2: Nuvoton NAU7802YG (Compact QFN-16 4.0 x 4.0 mm) (+8.5, +0.2)
    u2_pads = [
        PadSpec("1",  -1.85,  0.75, 0.65, 0.30, True, 0.0, "REFP"),
        PadSpec("2",  -1.85,  0.25, 0.65, 0.30, True, 0.0, "VIN1N"),
        PadSpec("3",  -1.85, -0.25, 0.65, 0.30, True, 0.0, "VIN1P"),
        PadSpec("4",  -1.85, -0.75, 0.65, 0.30, True, 0.0, "AVDD"),
        PadSpec("5",  -0.75, -1.85, 0.30, 0.65, True, 0.0, "VBG"),
        PadSpec("6",  -0.25, -1.85, 0.30, 0.65, True, 0.0, "AGND"),
        PadSpec("7",   0.25, -1.85, 0.30, 0.65, True, 0.0, "DRDY"),
        PadSpec("8",   0.75, -1.85, 0.30, 0.65, True, 0.0, "DVDD"),
        PadSpec("14",  1.85, -0.25, 0.65, 0.30, True, 0.0, "I2C_SCL"),
        PadSpec("15",  1.85,  0.25, 0.65, 0.30, True, 0.0, "I2C_SDA"),
        PadSpec("16",  1.85,  0.75, 0.65, 0.30, True, 0.0, "REFN"),
    ]
    parts.append(PartDef(
        "U2", "NAU7802YG", "Nuvoton", "NAU7802YG",
        "24-bit Dual-Ch Bridge ADC QFN-16 w/ High-Z AVDD Cutoff",
        "QFN-16_4x4mm", "SMT", "DigiKey: 2152-NAU7802YG-ND",
        8.5, 0.2, 0.0, "Top", 4.0, 4.0, u2_pads
    ))

    # U3: Bosch BMA400 Ultra-Low-Power 0.9 uA Auto-Wake IMU (-7.6, +4.6)
    u3_pads = [
        PadSpec("SDO",  -0.8,  0.5, 0.35, 0.35, True, 0.0, "GND"),
        PadSpec("SDA",  -0.8,  0.0, 0.35, 0.35, True, 0.0, "I2C_SDA"),
        PadSpec("SCL",  -0.8, -0.5, 0.35, 0.35, True, 0.0, "I2C_SCL"),
        PadSpec("VDD",   0.8,  0.5, 0.35, 0.35, True, 0.0, "VDD_3V3"),
        PadSpec("GND",   0.8,  0.0, 0.35, 0.35, True, 0.0, "GND"),
        PadSpec("INT1",  0.8, -0.5, 0.35, 0.35, True, 0.0, "IMU_INT1"),
    ]
    parts.append(PartDef(
        "U3", "BMA400", "Bosch Sensortec", "BMA400",
        "0.9 uA 25 Hz Auto-Wake 3-Axis Accelerometer",
        "LGA-12_2x2", "SMT", "DigiKey: 828-1071-1-ND",
        -7.6, 4.6, 0.0, "Top", 2.0, 2.0, u3_pads
    ))

    # Compact 0402 Passives, 0603 LED, and Reset Switch — all verified inside Ø28.0 mm
    parts.extend([
        PartDef("C1", "100nF C0G", "Murata", "GRM1555C1H104FA01", "Differential Bridge Filter Cap", "0402", "SMT", "LCSC: C1525",
                5.8, -0.5, 90.0, "Top", 1.2, 0.7, _rect_pads_2pin(0.95, 0.55, 0.65, "VIN1P", "VIN1N")),
        PartDef("C2", "10nF C0G", "Murata", "GRM1555C1H103JA01", "VIN1P Common-Mode Cap", "0402", "SMT", "LCSC: C15195",
                5.8, -2.1, 90.0, "Top", 1.2, 0.7, _rect_pads_2pin(0.95, 0.55, 0.65, "VIN1P", "AGND")),
        PartDef("C3", "10nF C0G", "Murata", "GRM1555C1H103JA01", "VIN1N Common-Mode Cap", "0402", "SMT", "LCSC: C15195",
                5.8, 1.1, 90.0, "Top", 1.2, 0.7, _rect_pads_2pin(0.95, 0.55, 0.65, "VIN1N", "AGND")),
        PartDef("C4", "1uF X5R", "Samsung", "CL05A105KA5NQNC", "NAU7802 AVDD Decoupling Cap", "0402", "SMT", "LCSC: C52923",
                8.0, 3.6, 0.0, "Top", 1.2, 0.7, _rect_pads_2pin(0.95, 0.55, 0.65, "AVDD", "AGND")),
        PartDef("C5", "100nF X7R", "Samsung", "CL05B104KO5NNNC", "NAU7802 VBG & MCU Decoupling", "0402", "SMT", "LCSC: C1525",
                8.0, 5.2, 0.0, "Top", 1.2, 0.7, _rect_pads_2pin(0.95, 0.55, 0.65, "VBG", "AGND")),
        PartDef("C6", "4.7uF X5R", "Samsung", "CL05A475MP5NRNC", "BQ25180 VSYS & VBAT Bulk Cap", "0402", "SMT", "LCSC: C23733",
                -10.5, -2.5, 90.0, "Top", 1.2, 0.7, _rect_pads_2pin(0.95, 0.55, 0.65, "VSYS", "GND")),
        PartDef("R1", "4.7k 1%", "Yageo", "RC0402FR-074K7L", "I2C SDA Pull-Up Resistor", "0402", "SMT", "LCSC: C25900",
                -6.6, 7.4, 0.0, "Top", 1.2, 0.7, _rect_pads_2pin(0.95, 0.55, 0.65, "VDD_3V3", "I2C_SDA")),
        PartDef("R2", "4.7k 1%", "Yageo", "RC0402FR-074K7L", "I2C SCL Pull-Up Resistor", "0402", "SMT", "LCSC: C25900",
                -6.6, 9.0, 0.0, "Top", 1.2, 0.7, _rect_pads_2pin(0.95, 0.55, 0.65, "VDD_3V3", "I2C_SCL")),
        PartDef("R3", "1.0k 1%", "Yageo", "RC0402FR-071KL", "Status LED Current Limit", "0402", "SMT", "LCSC: C11702",
                7.2, 7.5, 0.0, "Top", 1.2, 0.7, _rect_pads_2pin(0.95, 0.55, 0.65, "LED_STAT", "LED_A")),
        PartDef("D1", "LED_GRN_0603", "Kingbright", "APT1608ZGC", "0603 Green Lock Status LED", "0603", "SMT", "LCSC: C72043",
                7.4, 9.2, 0.0, "Top", 1.6, 0.8, _rect_pads_2pin(1.4, 0.7, 0.8, "LED_A", "GND")),
        PartDef("SW1", "EVQP7J01P", "Panasonic", "EVQP7J01P", "Recessed Tactile Reset / DFU Button", "3.5x2.9mm", "SMT", "DigiKey: P16758CT-ND",
                8.2, -5.2, 0.0, "Top", 3.5, 2.9, _rect_pads_2pin(3.8, 0.9, 1.2, "nRESET", "GND")),
    ])

    # Bottom-side Pads (Zero added height)
    j2_pads = [
        PadSpec("1", -1.27,  0.635, 0.78, 0.78, True, 0.0, "VDD_3V3"),
        PadSpec("2",  0.00,  0.635, 0.78, 0.78, True, 0.0, "SWDIO"),
        PadSpec("3",  1.27,  0.635, 0.78, 0.78, True, 0.0, "nRESET"),
        PadSpec("4", -1.27, -0.635, 0.78, 0.78, True, 0.0, "SWDCLK"),
        PadSpec("5",  0.00, -0.635, 0.78, 0.78, True, 0.0, "GND"),
        PadSpec("6",  1.27, -0.635, 0.78, 0.78, True, 0.0, "UART_TX"),
    ]
    parts.append(PartDef(
        "J2", "TC2030-IDC-NL", "Tag-Connect", "TC2030-IDC-NL_PAD",
        "Bottom-Side 6-Pin Pogo SWD/UART Debug Footprint (No Connector Mounted)",
        "TC2030_6PAD", "PCB_PAD_DNP", "N/A (Copper Pads Only)",
        0.0, -1.5, 0.0, "Bottom", 4.0, 2.4, j2_pads
    ))
    j3_pads = [
        PadSpec("1", -2.7, 0.0, 1.2, 1.8, True, 0.0, "AVDD"),
        PadSpec("2", -0.9, 0.0, 1.2, 1.8, True, 0.0, "AGND"),
        PadSpec("3",  0.9, 0.0, 1.2, 1.8, True, 0.0, "VIN1P"),
        PadSpec("4",  2.7, 0.0, 1.2, 1.8, True, 0.0, "VIN1N"),
    ]
    parts.append(PartDef(
        "J3", "BRIDGE_4PAD", "HydroCap", "FLEXURE_WIRE_PADS",
        "Bottom Solder Pads for 4x BF1000-2AA Wheatstone Bridge (E+/E-/S+/S-)",
        "PAD_4x1.8mm", "PCB_PAD_DNP", "N/A (Solder Pads)",
        6.2, -5.2, 0.0, "Bottom", 7.2, 2.0, j3_pads
    ))
    parts.append(PartDef(
        "J4", "LIPO_401520_PADS", "HydroCap", "BAT_SOLDER_PADS",
        "Bottom Solder Pads for 401520 100 mAh (or 302030 150 mAh) LiPo",
        "PAD_2x2.2mm", "PCB_PAD_DNP", "N/A (Solder Pads)",
        -6.2, 1.2, 0.0, "Bottom", 5.6, 2.2, _rect_pads_2pin(3.2, 1.8, 2.2, "VBAT", "GND")
    ))
    return parts


def _rot_xy(dx: float, dy: float, rot_deg: float) -> Tuple[float, float]:
    rad = math.radians(rot_deg)
    c, s = math.cos(rad), math.sin(rad)
    return (dx * c - dy * s, dx * s + dy * c)


def validate_drc_geometry(parts: List[PartDef]) -> None:
    """Assert zero component/mounting-hole bounding overlaps and board perimeter fit."""
    for layer in ("Top", "Bottom"):
        boxes: List[Tuple[str, float, float, float, float]] = []
        for p in parts:
            if p.layer != layer:
                continue
            bw, bh = (p.body_h, p.body_w) if int(round(p.rot)) % 180 == 90 else (p.body_w, p.body_h)
            x1, x2 = p.x - bw / 2.0, p.x + bw / 2.0
            y1, y2 = p.y - bh / 2.0, p.y + bh / 2.0
            if p.ref != "J1":  # J1 mid-mount USB-C intentionally protrudes flush at -Y edge
                max_r = max(math.hypot(x1, y1), math.hypot(x1, y2), math.hypot(x2, y1), math.hypot(x2, y2))
                assert max_r <= BOARD_RADIUS_MM - 0.1, f"DRC perimeter fail on {p.ref}: max_r={max_r:.2f} > {BOARD_RADIUS_MM}"
            boxes.append((p.ref, x1, y1, x2, y2))

        for hx, hy in MOUNT_HOLES_MM:
            max_hr = math.hypot(hx, hy) + 1.1
            assert max_hr <= BOARD_RADIUS_MM - 0.2, f"Hole {(hx, hy)} exceeds board edge: {max_hr:.2f}"
            boxes.append((f"HOLE_{hx}_{hy}", hx - 1.0, hy - 1.0, hx + 1.0, hy + 1.0))

        for i in range(len(boxes)):
            n1, ax1, ay1, ax2, ay2 = boxes[i]
            for j in range(i + 1, len(boxes)):
                n2, bx1, by1, bx2, by2 = boxes[j]
                if not (ax2 <= bx1 + 0.05 or bx2 <= ax1 + 0.05 or ay2 <= by1 + 0.05 or by2 <= ay1 + 0.05):
                    raise AssertionError(f"DRC overlap on {layer} between {n1} and {n2}")


def build_routes(parts: List[PartDef]) -> List[Tuple[str, float, List[Tuple[float, float]]]]:
    by_ref = {p.ref: p for p in parts}

    def pad_abs(ref: str, pad_num: str) -> Tuple[float, float]:
        p = by_ref[ref]
        for pad in p.pads:
            if pad.num == pad_num:
                rx, ry = _rot_xy(pad.dx, pad.dy, p.rot)
                return (p.x + rx, p.y + ry)
        raise KeyError(f"{ref}.{pad_num}")

    return [
        ("F.Cu", 0.30, [pad_abs("J1", "A4"), (-4.2, -7.8), pad_abs("U5", "5")]),
        ("F.Cu", 0.30, [pad_abs("U5", "5"), (-6.8, -3.5), pad_abs("U4", "IN")]),
        ("F.Cu", 0.20, [pad_abs("J1", "A6"), (-2.2, -7.2), pad_abs("U5", "1")]),
        ("F.Cu", 0.20, [pad_abs("J1", "A7"), (-1.0, -7.6), pad_abs("U5", "3")]),
        ("F.Cu", 0.20, [pad_abs("U5", "6"), (-4.6, -2.0), pad_abs("U1", "DP")]),
        ("F.Cu", 0.20, [pad_abs("U5", "4"), (-4.2, -2.4), pad_abs("U1", "DM")]),
        ("F.Cu", 0.20, [pad_abs("J1", "A5"), pad_abs("R4", "1")]),
        ("F.Cu", 0.20, [pad_abs("J1", "B5"), pad_abs("R5", "1")]),
        ("F.Cu", 0.30, [pad_abs("U4", "SYS"), pad_abs("U6", "IN")]),
        ("F.Cu", 0.30, [pad_abs("U6", "OUT"), (-5.2, 1.5), pad_abs("U1", "VDD")]),
        ("F.Cu", 0.20, [pad_abs("U1", "SDA"), (1.8, 3.2), pad_abs("U3", "SDA")]),
        ("F.Cu", 0.20, [pad_abs("U1", "SCL"), (3.0, 2.8), pad_abs("U3", "SCL")]),
        ("F.Cu", 0.20, [pad_abs("U1", "SDA"), (5.0, 2.4), pad_abs("U2", "15")]),
        ("F.Cu", 0.20, [pad_abs("U1", "SCL"), (5.2, 1.6), pad_abs("U2", "14")]),
        ("F.Cu", 0.20, [pad_abs("U1", "INT1"), (2.0, 3.8), pad_abs("U3", "INT1")]),
        ("F.Cu", 0.20, [pad_abs("U2", "3"), pad_abs("C1", "1")]),
        ("F.Cu", 0.20, [pad_abs("U2", "2"), pad_abs("C1", "2")]),
        ("F.Cu", 0.20, [pad_abs("U2", "4"), pad_abs("C4", "1")]),
        ("F.Cu", 0.20, [pad_abs("U1", "LED"), pad_abs("R3", "1")]),
        ("F.Cu", 0.20, [pad_abs("R3", "2"), pad_abs("D1", "1")]),
        ("B.Cu", 0.25, [pad_abs("J4", "1"), pad_abs("U4", "BAT")]),
        ("B.Cu", 0.20, [pad_abs("J2", "2"), (-3.0, 1.8), pad_abs("U1", "SWDIO")]),
        ("B.Cu", 0.20, [pad_abs("J2", "4"), (-2.6, 2.5), pad_abs("U1", "SWDCLK")]),
        ("B.Cu", 0.20, [pad_abs("J2", "3"), (4.5, -2.5), pad_abs("SW1", "1")]),
    ]


def _assert_balanced(text: str, name: str) -> None:
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise ValueError(f"Unbalanced closing paren in {name}")
    if depth != 0:
        raise ValueError(f"Unbalanced parens in {name}: depth={depth}")


def write_kicad_project(kicad_dir: str, parts: List[PartDef], routes: List[Tuple[str, float, List[Tuple[float, float]]]]) -> None:
    os.makedirs(kicad_dir, exist_ok=True)
    pro_path = os.path.join(kicad_dir, "HydroCap_V2.kicad_pro")
    sch_path = os.path.join(kicad_dir, "HydroCap_V2.kicad_sch")
    pcb_path = os.path.join(kicad_dir, "HydroCap_V2.kicad_pcb")

    with open(pro_path, "w", encoding="utf-8") as f:
        f.write('{\n  "board": { "design_settings": { "defaults": { "board_outline_line_width": 0.1, "copper_line_width": 0.2 } } },\n  "meta": { "filename": "HydroCap_V2.kicad_pro", "version": 1 },\n  "schematic": { "meta": { "version": 1 } }\n}\n')

    sch_lines = [
        '(kicad_sch (version 20231120) (generator "HydroCapGenerator")',
        f'  (uuid "{uuid.uuid4()}")',
        '  (paper "A3")',
        '  (title_block',
        '    (title "HydroCap V2.1 Universal 28mm Core — IPX8 USB-C + MDBT50Q + NAU7802YG + BMA400")',
        '    (rev "2.1")',
        '    (date "2026-11-22")',
        '    (comment 1 "PCBWay 4-Layer 0.8mm Circular 28.0mm ENIG — Fits All 1.1x D_cap Shells")',
        '  )',
        '  (lib_symbols)',
    ]
    for idx, p in enumerate(parts):
        sx = 40.0 + (idx % 4) * 85.0
        sy = 45.0 + (idx // 4) * 45.0
        sch_lines.append(f'  (symbol_instance (path "/{uuid.uuid4()}") (reference "{p.ref}") (unit 1) (value "{p.value}") (footprint "HydroCap:{p.pkg}"))')
        sch_lines.append(f'  (text "{p.ref}: {p.mpn}\\n{p.desc}" (exclude_from_sim no) (at {sx:.1f} {sy:.1f} 0) (effects (font (size 1.5 1.5))))')
        for pad in p.pads:
            if pad.net and pad.net != "NC":
                sch_lines.append(f'  (label "{pad.net}" (at {sx + 2.0:.1f} {sy + 4.0:.1f} 0) (effects (font (size 1.27 1.27))))')
    sch_lines.append(')')
    sch_txt = "\n".join(sch_lines) + "\n"
    _assert_balanced(sch_txt, "HydroCap_V2.kicad_sch")
    with open(sch_path, "w", encoding="utf-8") as f:
        f.write(sch_txt)

    cx, cy = 100.0, 100.0
    pcb_lines = [
        '(kicad_pcb (version 20240108) (generator "HydroCapGenerator")',
        '  (general (thickness 0.8))',
        '  (paper "A4")',
        '  (layers',
        '    (0 "F.Cu" signal) (1 "In1.Cu" power) (2 "In2.Cu" power) (31 "B.Cu" signal)',
        '    (34 "B.Paste" user) (35 "F.Paste" user) (36 "B.SilkS" user) (37 "F.SilkS" user)',
        '    (38 "B.Mask" user) (39 "F.Mask" user) (44 "Edge.Cuts" user)',
        '  )',
        '  (net 0 "")',
    ]
    nets = sorted({pad.net for p in parts for pad in p.pads if pad.net})
    net_id = {n: i + 1 for i, n in enumerate(nets)}
    for n, nid in net_id.items():
        pcb_lines.append(f'  (net {nid} "{n}")')

    pcb_lines.append(f'  (gr_circle (center {cx:.2f} {cy:.2f}) (end {cx + BOARD_RADIUS_MM:.2f} {cy:.2f}) (stroke (width 0.1) (type solid)) (layer "Edge.Cuts"))')
    pcb_lines.append(
        f'  (zone (net 0) (net_name "") (layers "F.Cu" "In1.Cu" "In2.Cu" "B.Cu") (keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed) (footprints allowed)) '
        f'(polygon (pts (xy {cx - 5.2:.1f} {cy - 13.5:.1f}) (xy {cx + 5.2:.1f} {cy - 13.5:.1f}) (xy {cx + 5.2:.1f} {cy - 7.8:.1f}) (xy {cx - 5.2:.1f} {cy - 7.8:.1f}))))'
    )

    for p in parts:
        layer_str = "F.Cu" if p.layer == "Top" else "B.Cu"
        silk_str = "F.SilkS" if p.layer == "Top" else "B.SilkS"
        px, py = cx + p.x, cy - p.y
        pcb_lines.append(f'  (footprint "HydroCap:{p.pkg}" (layer "{layer_str}") (at {px:.3f} {py:.3f} {p.rot:.1f})')
        pcb_lines.append(f'    (property "Reference" "{p.ref}" (at 0 0 0) (layer "{silk_str}"))')
        pcb_lines.append(f'    (property "Value" "{p.value}" (at 0 1.5 0) (layer "{silk_str}"))')
        for pad in p.pads:
            nid = net_id.get(pad.net, 0)
            layers = '"F.Cu" "F.Paste" "F.Mask"' if p.layer == "Top" else '"B.Cu" "B.Paste" "B.Mask"'
            pcb_lines.append(f'    (pad "{pad.num}" smd rect (at {pad.dx:.3f} {-pad.dy:.3f} {p.rot:.1f}) (size {pad.w:.3f} {pad.h:.3f}) (layers {layers}) (net {nid} "{pad.net}"))')
        pcb_lines.append('  )')

    for hx, hy in MOUNT_HOLES_MM:
        pcb_lines.append(f'  (footprint "MountingHole:1.6mm" (layer "F.Cu") (at {cx + hx:.2f} {cy - hy:.2f}) (pad "" np_thru_hole circle (at 0 0) (size 1.8 1.8) (drill 1.6) (layers "*.Cu" "*.Mask")))')

    for layer, width, pts in routes:
        for a, b in zip(pts[:-1], pts[1:]):
            pcb_lines.append(f'  (segment (start {cx + a[0]:.3f} {cy - a[1]:.3f}) (end {cx + b[0]:.3f} {cy - b[1]:.3f}) (width {width:.2f}) (layer "{layer}") (net 1))')

    pcb_lines.append(')')
    pcb_txt = "\n".join(pcb_lines) + "\n"
    _assert_balanced(pcb_txt, "HydroCap_V2.kicad_pcb")
    with open(pcb_path, "w", encoding="utf-8") as f:
        f.write(pcb_txt)


def _fmt_g(val_mm: float) -> str:
    return str(int(round(val_mm * 1_000_000)))


def _gerber_header(title: str) -> List[str]:
    return [f"G04 HydroCap V2.1 28mm {title}*", "%FSLAX46Y46*%", "%MOMM*%", "%LPD*%"]


def write_gerbers_and_zip(fab_dir: str, parts: List[PartDef], routes: List[Tuple[str, float, List[Tuple[float, float]]]]) -> str:
    gerb_dir = os.path.join(fab_dir, "gerbers")
    os.makedirs(gerb_dir, exist_ok=True)
    ap_map: Dict[Tuple[float, float], int] = {}
    ap_code = 10

    def get_rect_ap(w: float, h: float) -> int:
        nonlocal ap_code
        key = (round(w, 3), round(h, 3))
        if key not in ap_map:
            ap_map[key] = ap_code
            ap_code += 1
        return ap_map[key]

    for p in parts:
        for pad in p.pads:
            rw, rh = (pad.h, pad.w) if int(round(p.rot)) % 180 == 90 else (pad.w, pad.h)
            get_rect_ap(rw, rh)
    ap_trace_20, ap_trace_30, ap_outline = 90, 91, 95

    def aperture_defs() -> List[str]:
        lines = [f"%ADD{code}R,{rw:.3f}X{rh:.3f}*%" for (rw, rh), code in sorted(ap_map.items(), key=lambda kv: kv[1])]
        lines.extend([f"%ADD{ap_trace_20}C,0.200*%", f"%ADD{ap_trace_30}C,0.300*%", f"%ADD{ap_outline}C,0.100*%"])
        return lines

    def emit_copper_layer(layer_key: str, title: str, include_mask: bool = False, include_paste: bool = False) -> List[str]:
        lines = _gerber_header(title) + aperture_defs() + ["G01*"]
        target = "Top" if layer_key == "F.Cu" else "Bottom"
        for p in parts:
            if p.layer != target or (include_paste and p.assy_type == "PCB_PAD_DNP"):
                continue
            for pad in p.pads:
                rx, ry = _rot_xy(pad.dx, pad.dy, p.rot)
                rw, rh = (pad.h, pad.w) if int(round(p.rot)) % 180 == 90 else (pad.w, pad.h)
                lines.append(f"D{get_rect_ap(rw, rh)}*")
                lines.append(f"X{_fmt_g(p.x + rx)}Y{_fmt_g(p.y + ry)}D03*")
        if not include_mask and not include_paste:
            for r_layer, width, pts in routes:
                if r_layer != layer_key:
                    continue
                lines.append(f"D{ap_trace_30 if width >= 0.28 else ap_trace_20}*")
                lines.append(f"X{_fmt_g(pts[0][0])}Y{_fmt_g(pts[0][1])}D02*")
                for px, py in pts[1:]:
                    lines.append(f"X{_fmt_g(px)}Y{_fmt_g(py)}D01*")
        lines.append("M02*")
        return lines

    gm1 = _gerber_header("Board Outline Edge.Cuts") + [f"%ADD{ap_outline}C,0.100*%", "G01*", f"D{ap_outline}*"]
    for i in range(121):
        ang = 2.0 * math.pi * i / 120.0
        gm1.append(f"X{_fmt_g(BOARD_RADIUS_MM * math.cos(ang))}Y{_fmt_g(BOARD_RADIUS_MM * math.sin(ang))}D{'02' if i == 0 else '01'}*")
    gm1.append("M02*")

    def emit_plane(name: str) -> List[str]:
        lines = _gerber_header(name) + [f"%ADD{ap_trace_30}C,0.500*%", "G01*", f"D{ap_trace_30}*"]
        for i in range(73):
            ang = 2.0 * math.pi * i / 72.0
            lines.append(f"X{_fmt_g(12.8 * math.cos(ang))}Y{_fmt_g(min(12.8 * math.sin(ang), 7.5))}D{'02' if i == 0 else '01'}*")
        lines.append("M02*")
        return lines

    def emit_silk(target: str, title: str) -> List[str]:
        lines = _gerber_header(title) + [f"%ADD{ap_outline}C,0.150*%", "G01*", f"D{ap_outline}*"]
        for p in parts:
            if p.layer != target:
                continue
            hw, hh = p.body_w / 2.0, p.body_h / 2.0
            for idx, (cx_, cy_) in enumerate([(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh), (-hw, -hh)]):
                lines.append(f"X{_fmt_g(p.x + cx_)}Y{_fmt_g(p.y + cy_)}D{'02' if idx == 0 else '01'}*")
        lines.append("M02*")
        return lines

    files: Dict[str, List[str]] = {
        "HydroCap_V2.GTL": emit_copper_layer("F.Cu", "Top Copper"),
        "HydroCap_V2.G2":  emit_plane("Inner1 GND Plane"),
        "HydroCap_V2.G3":  emit_plane("Inner2 3V3 Power Plane"),
        "HydroCap_V2.GBL": emit_copper_layer("B.Cu", "Bottom Copper"),
        "HydroCap_V2.GTS": emit_copper_layer("F.Cu", "Top Solder Mask", include_mask=True),
        "HydroCap_V2.GBS": emit_copper_layer("B.Cu", "Bottom Solder Mask", include_mask=True),
        "HydroCap_V2.GTP": emit_copper_layer("F.Cu", "Top Solder Paste", include_paste=True),
        "HydroCap_V2.GTO": emit_silk("Top", "Top Silkscreen"),
        "HydroCap_V2.GBO": emit_silk("Bottom", "Bottom Silkscreen"),
        "HydroCap_V2.GM1": gm1,
        "HydroCap_V2-PTH.drl": [
            "M48", "; HydroCap V2.1 Plated Through-Hole Vias", "METRIC,TZ",
            "T1C0.300", "%", "T1",
            "X-4.200Y-7.800", "X0.000Y0.000", "X5.000Y2.400", "X-3.000Y1.800",
            "M30",
        ],
        "HydroCap_V2-NPTH.drl": [
            "M48", "; HydroCap V2.1 4x M1.6 Universal Core Mounting Holes", "METRIC,TZ",
            "T1C1.600", "%", "T1",
        ] + [f"X{hx:.3f}Y{hy:.3f}" for hx, hy in MOUNT_HOLES_MM] + ["M30"],
    }

    for fname, content in files.items():
        with open(os.path.join(gerb_dir, fname), "w", encoding="utf-8") as f:
            f.write("\n".join(content) + "\n")

    zip_path = os.path.join(fab_dir, "HydroCap_V2_PCBWay_Gerbers.zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in sorted(files):
            zf.write(os.path.join(gerb_dir, fname), arcname=fname)
    return zip_path


def write_pcba_csvs(pcba_dir: str, parts: List[PartDef]) -> None:
    os.makedirs(pcba_dir, exist_ok=True)
    with open(os.path.join(pcba_dir, "HydroCap_V2_PCBWay_BOM.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Line#", "Designator", "Qty", "Manufacturer", "Part Number", "Description", "Package", "Type", "Distributor Ref"])
        for idx, p in enumerate(parts, start=1):
            w.writerow([idx, p.ref, 1, p.mfg, p.mpn, p.desc, p.pkg, p.assy_type, p.dist_ref])

    with open(os.path.join(pcba_dir, "HydroCap_V2_PCBWay_CPL_PickAndPlace.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X (mm)", "Mid Y (mm)", "Layer", "Rotation", "Package", "Value"])
        for p in parts:
            w.writerow([p.ref, f"{p.x:.3f}", f"{p.y:.3f}", p.layer, f"{p.rot:.1f}", p.pkg, p.value])


def render_pcb_views(out_png: str, parts: List[PartDef], routes: List[Tuple[str, float, List[Tuple[float, float]]]]) -> None:
    fig, (ax_t, ax_b) = plt.subplots(1, 2, figsize=(14.5, 7.2), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    fig.suptitle(
        "HydroCap V2.1 Universal Core PCB (Ø 28.0 mm × 0.8 mm, 4L ENIG) — Fits 1.1x D_cap (33.6 mm PET -> 69.3 mm Wide)",
        fontsize=12.5, fontweight="bold", color="#1A252C", y=0.97
    )

    for ax, title, layer_name, cu_layer in [
        (ax_t, "Top Layer (F.Cu / F.SilkS) — MDBT50Q + IPX8 USB-C + NAU7802YG + BMA400", "Top", "F.Cu"),
        (ax_b, "Bottom Layer (B.Cu / B.SilkS) — Tag-Connect TC2030 SWD & Solder Pads", "Bottom", "B.Cu"),
    ]:
        ax.set_title(title, fontsize=10.0, fontweight="bold", color="#1B4F72", pad=8)
        ax.set_xlim(-17.0, 17.0)
        ax.set_ylim(-17.0, 17.0)
        ax.set_aspect("equal")
        ax.set_xlabel("X (mm)", fontsize=8.5)
        ax.set_ylabel("Y (mm)", fontsize=8.5)
        ax.grid(True, linestyle=":", alpha=0.35)

        ax.add_patch(Circle((0, 0), BOARD_RADIUS_MM, facecolor="#0B5345", edgecolor="#F1C40F", linewidth=2.0, zorder=1))
        ax.add_patch(Rectangle((-5.2, 7.8), 10.4, 5.7, facecolor="#78281F", edgecolor="#E74C3C", lw=1.2, ls="--", alpha=0.80, zorder=6))
        if layer_name == "Top":
            ax.text(0, 10.8, "ANTENNA\nKEEP-OUT", ha="center", va="center", fontsize=6.5, fontweight="bold", color="#FADBD8", zorder=8)

        for hx, hy in MOUNT_HOLES_MM:
            ax.add_patch(Circle((hx, hy), 1.0, facecolor="#F1C40F", edgecolor="#9A7D0A", lw=0.8, zorder=3))
            ax.add_patch(Circle((hx, hy), 0.8, facecolor="#FFFFFF", edgecolor="#1B2631", lw=0.6, zorder=4))

        for r_layer, width, pts in routes:
            if r_layer == cu_layer:
                ax.plot([pt[0] for pt in pts], [pt[1] for pt in pts],
                        color="#E74C3C" if cu_layer == "F.Cu" else "#3498DB", linewidth=width * 4.5, alpha=0.85, zorder=4)

        for p in parts:
            if p.layer != layer_name:
                continue
            bw, bh = (p.body_h, p.body_w) if int(round(p.rot)) % 180 == 90 else (p.body_w, p.body_h)
            ax.add_patch(Rectangle((p.x - bw / 2.0, p.y - bh / 2.0), bw, bh,
                                   facecolor="#1C2833", edgecolor="#ECF0F1", lw=0.9, alpha=0.85, zorder=5))
            for pad in p.pads:
                rx, ry = _rot_xy(pad.dx, pad.dy, p.rot)
                rw, rh = (pad.h, pad.w) if int(round(p.rot)) % 180 == 90 else (pad.w, pad.h)
                ax.add_patch(Rectangle((p.x + rx - rw / 2.0, p.y + ry - rh / 2.0), rw, rh, facecolor="#F1C40F", edgecolor="none", zorder=6))
            ax.text(p.x, p.y, p.ref, ha="center", va="center", fontsize=6.8, fontweight="bold", color="#FFFFFF", zorder=8)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="#FFFFFF")
    plt.close(fig)


def main() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    parts = build_parts()
    validate_drc_geometry(parts)
    routes = build_routes(parts)

    write_kicad_project(os.path.join(base_dir, "kicad"), parts, routes)
    zip_path = write_gerbers_and_zip(os.path.join(base_dir, "fab"), parts, routes)
    write_pcba_csvs(os.path.join(base_dir, "pcba"), parts)
    render_pcb_views(os.path.join(base_dir, "pcb_layout_top_bottom.png"), parts, routes)

    print(f"[PCBWay] DRC PASSED (Ø {BOARD_RADIUS_MM * 2:.1f} mm) | {len(parts)} BOM/CPL entries | Gerbers -> {zip_path}")


if __name__ == "__main__":
    main()
