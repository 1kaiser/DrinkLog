#!/usr/bin/env python3
"""
Generate zero-overlap Draw.io XML schematics/flowcharts and matching high-DPI
matplotlib PNG renders for the DrinkLog Smart Bottle-Cap Hydration Tracker.
"""

from __future__ import annotations

import html
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


@dataclass
class NodeDef:
    nid: str
    title: str
    body_lines: List[str]
    x: float
    y: float
    w: float
    h: float
    fill: str
    stroke: str
    title_color: str = "#1B2631"
    parent: str = "1"
    kind: str = "process"  # "group" | "process" | "terminator" | "decision"
    arc: int = 10


@dataclass
class EdgeDef:
    eid: str
    src: str
    dst: str
    points: List[Tuple[float, float]]
    color: str
    label: str = ""
    width: float = 2.2
    dashed: bool = False
    label_pos: Optional[Tuple[float, float]] = None


def _drawio_style(node: NodeDef) -> str:
    base = "html=1;whiteSpace=wrap;overflow=hidden;fontFamily=Helvetica;"
    if node.kind == "group":
        return (
            f"rounded=1;arcSize=6;fillColor={node.fill};strokeColor={node.stroke};"
            f"strokeWidth=1.8;dashed=1;verticalAlign=top;align=left;spacingTop=8;"
            f"spacingLeft=12;fontSize=13;fontStyle=1;fontColor={node.title_color};{base}"
        )
    if node.kind == "terminator":
        return (
            f"rounded=1;arcSize=50;fillColor={node.fill};strokeColor={node.stroke};"
            f"strokeWidth=2.0;align=center;verticalAlign=middle;spacing=6;"
            f"fontSize=12;fontColor={node.title_color};{base}"
        )
    if node.kind == "decision":
        return (
            f"rhombus;fillColor={node.fill};strokeColor={node.stroke};"
            f"strokeWidth=2.0;align=center;verticalAlign=middle;spacing=4;"
            f"fontSize=11;fontColor={node.title_color};{base}"
        )
    return (
        f"rounded=1;arcSize={node.arc};fillColor={node.fill};strokeColor={node.stroke};"
        f"strokeWidth=1.8;align=center;verticalAlign=middle;spacingTop=6;"
        f"spacingBottom=6;spacingLeft=8;spacingRight=8;fontSize=11.5;"
        f"fontColor={node.title_color};{base}"
    )


def _drawio_label_html(node: NodeDef) -> str:
    if node.kind == "group":
        return f"<b>{html.escape(node.title)}</b>"
    parts = [f"<b>{html.escape(node.title)}</b>"]
    for line in node.body_lines:
        parts.append(html.escape(line))
    return "<br/>".join(parts)


def write_drawio_xml(
    out_path: str,
    title: str,
    width: int,
    height: int,
    nodes: List[NodeDef],
    edges: List[EdgeDef],
) -> None:
    mxfile = ET.Element("mxfile", host="DrinkLogGenerator", type="device")
    diagram = ET.SubElement(mxfile, "diagram", id="cap_diagram", name=title)
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        dx="1200",
        dy="800",
        grid="1",
        gridSize="10",
        guides="1",
        tooltips="1",
        connect="1",
        arrows="1",
        fold="1",
        page="1",
        pageScale="1",
        pageWidth=str(width),
        pageHeight=str(height),
        math="0",
        shadow="0",
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    node_map: Dict[str, NodeDef] = {n.nid: n for n in nodes}

    # Emit groups first so child cells sit above them in z-order
    ordered = [n for n in nodes if n.kind == "group"] + [n for n in nodes if n.kind != "group"]
    for n in ordered:
        rel_x, rel_y = n.x, n.y
        if n.parent != "1" and n.parent in node_map:
            p = node_map[n.parent]
            rel_x = n.x - p.x
            rel_y = n.y - p.y

        cell = ET.SubElement(
            root,
            "mxCell",
            id=n.nid,
            value=_drawio_label_html(n),
            style=_drawio_style(n),
            vertex="1",
            parent=n.parent,
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            x=str(round(rel_x, 1)),
            y=str(round(rel_y, 1)),
            width=str(round(n.w, 1)),
            height=str(round(n.h, 1)),
            **{"as": "geometry"},
        )

    for e in edges:
        dash = "dashed=1;dashPattern=6 4;" if e.dashed else ""
        style = (
            f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;"
            f"strokeColor={e.color};strokeWidth={e.width};{dash}"
            f"endArrow=classic;endFill=1;endSize=7;fontSize=10.5;fontStyle=1;"
            f"fontColor={e.color};labelBackgroundColor=#FFFFFF;"
        )
        ecell = ET.SubElement(
            root,
            "mxCell",
            id=e.eid,
            value=e.label,
            style=style,
            edge="1",
            source=e.src,
            target=e.dst,
            parent="1",
        )
        geo = ET.SubElement(ecell, "mxGeometry", relative="1", **{"as": "geometry"})
        if len(e.points) >= 2:
            sp = e.points[0]
            tp = e.points[-1]
            ET.SubElement(geo, "mxPoint", x=str(sp[0]), y=str(sp[1]), **{"as": "sourcePoint"})
            ET.SubElement(geo, "mxPoint", x=str(tp[0]), y=str(tp[1]), **{"as": "targetPoint"})
            if len(e.points) > 2:
                arr = ET.SubElement(geo, "Array", **{"as": "points"})
                for px, py in e.points[1:-1]:
                    ET.SubElement(arr, "mxPoint", x=str(px), y=str(py))

    tree = ET.ElementTree(mxfile)
    ET.indent(tree, space="  ")
    tree.write(out_path, encoding="utf-8", xml_declaration=True)


def render_png(
    out_path: str,
    banner_title: str,
    banner_sub: str,
    width: int,
    height: int,
    nodes: List[NodeDef],
    edges: List[EdgeDef],
) -> None:
    fig_w = width / 110.0
    fig_h = (height + 70) / 110.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=200)
    ax.set_xlim(0, width)
    ax.set_ylim(height + 15, -65)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    # Title banner
    ax.text(
        width / 2.0, -40, banner_title,
        ha="center", va="center", fontsize=14, fontweight="bold", color="#1A252C",
        fontfamily="DejaVu Sans",
    )
    ax.text(
        width / 2.0, -17, banner_sub,
        ha="center", va="center", fontsize=9.5, color="#4A5568",
        fontfamily="DejaVu Sans",
    )

    # Draw groups first
    for n in [x for x in nodes if x.kind == "group"]:
        patch = FancyBboxPatch(
            (n.x, n.y), n.w, n.h,
            boxstyle="round,pad=0,rounding_size=10",
            facecolor=n.fill, edgecolor=n.stroke, linewidth=1.5, linestyle="--", zorder=1
        )
        ax.add_patch(patch)
        ax.text(
            n.x + 12, n.y + 18, n.title,
            ha="left", va="center", fontsize=9.5, fontweight="bold", color=n.title_color,
            zorder=2, fontfamily="DejaVu Sans",
        )

    # Draw edges next (below nodes except arrowheads)
    for e in edges:
        ls = "--" if e.dashed else "-"
        xs = [p[0] for p in e.points]
        ys = [p[1] for p in e.points]
        if len(xs) >= 2:
            if len(xs) > 2:
                ax.plot(xs[:-1], ys[:-1], color=e.color, linewidth=e.width * 0.9,
                        linestyle=ls, solid_capstyle="butt", zorder=3)
            arr = FancyArrowPatch(
                (xs[-2], ys[-2]), (xs[-1], ys[-1]),
                arrowstyle="-|>", mutation_scale=13,
                color=e.color, linewidth=e.width * 0.9, linestyle=ls, zorder=4
            )
            ax.add_patch(arr)
            if e.label:
                if e.label_pos is not None:
                    lx, ly = e.label_pos
                else:
                    lx = 0.5 * (xs[0] + xs[-1])
                    ly = 0.5 * (ys[0] + ys[-1])
                ax.text(
                    lx, ly, e.label,
                    ha="center", va="center", fontsize=8.0, fontweight="bold",
                    color=e.color, zorder=7,
                    bbox=dict(boxstyle="round,pad=0.22", facecolor="#FFFFFF", edgecolor="none", alpha=0.92),
                )

    # Draw foreground nodes
    for n in [x for x in nodes if x.kind != "group"]:
        if n.kind == "decision":
            cx, cy = n.x + n.w / 2.0, n.y + n.h / 2.0
            poly = plt.Polygon(
                [(cx, n.y), (n.x + n.w, cy), (cx, n.y + n.h), (n.x, cy)],
                closed=True, facecolor=n.fill, edgecolor=n.stroke, linewidth=1.8, zorder=5
            )
            ax.add_patch(poly)
        else:
            r = min(n.h / 2.0, 24.0) if n.kind == "terminator" else 8.0
            patch = FancyBboxPatch(
                (n.x, n.y), n.w, n.h,
                boxstyle=f"round,pad=0,rounding_size={r}",
                facecolor=n.fill, edgecolor=n.stroke, linewidth=1.7, zorder=5
            )
            ax.add_patch(patch)

        cx = n.x + n.w / 2.0
        total_lines = 1 + len(n.body_lines)
        cy = n.y + n.h / 2.0
        line_h = 13.5 if n.kind != "decision" else 12.0
        start_y = cy - ((total_lines - 1) * line_h) / 2.0

        ax.text(
            cx, start_y, n.title,
            ha="center", va="center", fontsize=8.8, fontweight="bold",
            color=n.title_color, zorder=6, fontfamily="DejaVu Sans",
        )
        for idx, line in enumerate(n.body_lines, start=1):
            ax.text(
                cx, start_y + idx * line_h, line,
                ha="center", va="center", fontsize=7.6, color="#2D3748",
                zorder=6, fontfamily="DejaVu Sans",
            )

    plt.tight_layout(pad=0.4)
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="#FFFFFF")
    plt.close(fig)


# ===========================================================================
# Diagram 1: System Electrical Block & Power-Gating Schematic
# ===========================================================================
def build_circuit_schematic(out_dir: str) -> None:
    W, H = 1380, 780

    nodes = [
        # Background functional groups (deliberate nesting containers)
        NodeDef("grp_pwr", "POWER & CHARGING STAGE", [], 30, 30, 290, 710, "#FEF9E7", "#D4AC0D", "#7D6608", kind="group"),
        NodeDef("grp_mcu", "BLE MCU CORE & MOTION WAKE", [], 370, 30, 440, 710, "#EBF5FB", "#2980B9", "#1B4F72", kind="group"),
        NodeDef("grp_afe", "LOAD-SENSING ANALOG FRONT END", [], 860, 30, 490, 710, "#EAFAF1", "#27AE60", "#145A32", kind="group"),

        # Left column: Power + Waterproof USB-C
        NodeDef("pogo", "IPX8 USB-C (12402448E512A)", ["Mid-Mount O-Ring + TPU Plug", "5.1k CC1/CC2 + USBLC6 ESD"], 60, 90, 230, 88, "#FFFDF5", "#D4AC0D", parent="grp_pwr"),
        NodeDef("charger", "LiPo Charger PMIC", ["V1: XIAO BQ25101", "V2: TI BQ25180 (I2C, 3 uA Iq)", "15 nA Ship Mode"], 60, 235, 230, 100, "#FFFDF5", "#D4AC0D", parent="grp_pwr"),
        NodeDef("lipo", "302030 LiPo (150 mAh)", ["3.7V Pouch w/ Built-in PCM", "Alt V2: Varta CP1254 (4.00V)", "3.0 mm Thick"], 60, 395, 230, 100, "#FDF2E9", "#D35400", parent="grp_pwr"),
        NodeDef("ldo", "3.3V LDO & VBAT Monitor", ["V2: TPS7A0233 (25 nA Iq)", "V1: P0.14 LOW 1ms -> P0.31"], 60, 565, 230, 105, "#FFFDF5", "#2980B9", parent="grp_pwr"),

        # Center column: MCU + Wake IMU
        NodeDef("mcu", "nRF52840 (XIAO / MDBT50Q)", ["Primary V1: XIAO nRF52840 (~5 uA)", "V2 PCBWay: MDBT50Q + TC2030 SWD", "Native USB 2.0 D+/D- CDC & DFU", "Alt V1C: XIAO ESP32-C6 (17 uA)"], 410, 90, 360, 140, "#FFFFFF", "#2980B9", parent="grp_mcu"),
        NodeDef("imu", "Bosch BMA400 Wake IMU", ["I2C Addr 0x14 (SDO=GND)", "25 Hz Auto-Wake (~0.9 uA)", "INT1 -> D1 (Wake on Lift)", "Static Hold Gate (az ~ 1.0g)"], 410, 305, 360, 125, "#FFFFFF", "#2980B9", parent="grp_mcu"),
        NodeDef("ble", "BLE 5.0 GATT + 64-Event Ring", ["0 dBm TX (~5-8 mA burst)", "Svc 0001 | Ev 0002 (12 B)", "ACK 0003 (4 B) | Stat 0004 (8 B)"], 410, 515, 360, 125, "#F4ECF7", "#8E44AD", parent="grp_mcu"),

        # Right column: Bridge ADC & Sensors
        NodeDef("nau", "Nuvoton NAU7802 (24-bit ADC)", ["I2C Addr 0x2A | DVDD = 3.3V", "Internal AVDD LDO = 2.4V (>=10mA)", "Sleep PUA=0, PUD=0 (< 1 uA)", "AVDD -> High-Z (0 uA Bridge Leak)"], 900, 90, 415, 130, "#FFFFFF", "#27AE60", parent="grp_afe"),
        NodeDef("filter", "Differential Analog RC Filter", ["100 nF C0G across VIN1P-VIN1N", "10 nF C0G CM caps to AGND", "1 uF on AVDD | 100 nF on VBG"], 900, 290, 415, 105, "#FFFFFF", "#27AE60", parent="grp_afe"),
        NodeDef("bridge", "1000 Ohm Full Wheatstone Bridge", ["4x BF1000-3AA on 0.8mm 301-SS", "3-Spoke 120-deg Moment Flexure", "Active Draw: 2.4mA @ 2.4V", "Hard-Stop Guard at 0.35 mm"], 900, 460, 415, 125, "#EAFAF1", "#1E8449", parent="grp_afe"),
        NodeDef("fx29", "Alt V1A: TE FX29 I2C Load Cell", ["14-bit I2C (0x28), 10 lbf / 4.5 kg", "0.5 uA Sleep | Pull-to-Compress Yoke"], 900, 625, 415, 85, "#FEF9E7", "#B7950B", dashed=False if False else True, parent="grp_afe") if False else
        NodeDef("fx29", "Alt V1A: TE FX29 I2C Load Cell", ["14-bit I2C (0x28), 10 lbf / 4.5 kg", "0.5 uA Sleep | Pull-to-Compress Yoke"], 900, 625, 415, 85, "#FEF9E7", "#B7950B", parent="grp_afe"),
    ]

    # Carefully assigned non-colliding orthogonal waypoints in open channels
    edges = [
        EdgeDef("e_vbus", "pogo", "charger", [(175, 178), (175, 235)], "#B7950B", "5V VBUS"),
        EdgeDef("e_usbc_data", "pogo", "mcu", [(290, 128), (410, 128)], "#8E44AD", "USB D+/D-", label_pos=(350, 113)),
        EdgeDef("e_bat", "charger", "lipo", [(175, 335), (175, 395)], "#D35400", "Charge / PCM", label_pos=(225, 365)),
        EdgeDef("e_ldo", "lipo", "ldo", [(175, 495), (175, 565)], "#2980B9", "VBAT 3.7V", label_pos=(225, 530)),
        EdgeDef("e_3v3_mcu", "ldo", "mcu", [(290, 617), (345, 617), (345, 180), (410, 180)], "#2980B9", "3.3V + P0.31", label_pos=(345, 380)),
        EdgeDef("e_int1", "imu", "mcu", [(485, 305), (485, 230)], "#C0392B", "INT1 -> D1 (Wake)", label_pos=(485, 268)),
        EdgeDef("e_i2c_imu", "mcu", "imu", [(695, 230), (695, 305)], "#1F618D", "I2C SDA/SCL (D4/D5)", label_pos=(732, 268)),
        EdgeDef("e_ble", "mcu", "ble", [(590, 230), (590, 265), (390, 265), (390, 577), (410, 577)], "#8E44AD", "Ring Events", label_pos=(390, 440)),
        EdgeDef("e_i2c_nau", "mcu", "nau", [(770, 145), (900, 145)], "#1E8449", "I2C 0x2A + DRDY", label_pos=(835, 128)),
        EdgeDef("e_i2c_fx", "mcu", "fx29", [(770, 185), (835, 185), (835, 667), (900, 667)], "#B7950B", "Alt I2C 0x28", dashed=True, label_pos=(835, 455)),
        EdgeDef("e_nau_flt", "nau", "filter", [(1107, 220), (1107, 290)], "#27AE60", "VIN1P/N + AVDD", label_pos=(1160, 255)),
        EdgeDef("e_flt_br", "filter", "bridge", [(1107, 395), (1107, 460)], "#1E8449", "2.4V Gated Exc.", label_pos=(1160, 428)),
    ]

    xml_path = os.path.join(out_dir, "system_circuit_schematic.drawio")
    png_path = os.path.join(out_dir, "system_circuit_schematic.png")
    write_drawio_xml(xml_path, "DrinkLog_System_Circuit", W, H, nodes, edges)
    render_png(
        png_path,
        "DrinkLog Hardware Architecture, IPX8 USB-C Debug & Power-Gating Schematic",
        "Standby ~6.4 uA (MDBT50Q / XIAO nRF52840 + BMA400 + NAU7802 High-Z AVDD) | PCBWay 4-Layer V2",
        W,
        H,
        nodes,
        edges,
    )


# ===========================================================================
# Diagram 2: End-to-End Firmware + BLE + Health Connect Pipeline
# ===========================================================================
def build_firmware_pipeline(out_dir: str) -> None:
    W, H = 1280, 980

    nodes = [
        NodeDef("grp_cap", "CAP FIRMWARE (nRF52840 / ESP32-C6)", [], 30, 30, 770, 910, "#F8F9F9", "#5D6D7E", "#1C2833", kind="group"),
        NodeDef("grp_phone", "ANDROID COMPANION & HEALTH CONNECT", [], 850, 30, 400, 910, "#F4ECF7", "#8E44AD", "#4A235A", kind="group"),

        NodeDef("n_sleep", "System-ON Deep Sleep (~6.5 uA)", ["AVDD = High-Z (0 uA bridge), BMA400 @ 25 Hz"], 200, 90, 390, 68, "#EBF5FB", "#2980B9", kind="terminator", parent="grp_cap"),
        NodeDef("n_wake", "BMA400 Motion Interrupt (INT1 -> D1)", ["Wakes MCU; Poll IMU at 20 Hz for 300 ms hold"], 200, 200, 390, 68, "#FFFFFF", "#2980B9", parent="grp_cap"),
        NodeDef("d_still", "Static Vertical Hold?", ["az in [0.85g, 1.15g] & tilt < 15 deg"], 235, 310, 320, 95, "#FEF9E7", "#D4AC0D", kind="decision", parent="grp_cap"),
        NodeDef("n_sample", "Power AVDD (2.4V) & Sample ADC", ["80 ms settle, 15x NAU7802 -> median_filter_15()", "Power-Down AVDD -> High-Z immediately"], 200, 455, 390, 76, "#EAFAF1", "#27AE60", parent="grp_cap"),
        NodeDef("d_unscrew", "|raw_g| < 45 g?", ["(Cap Unscrewed?)"], 255, 575, 280, 88, "#FEF9E7", "#D4AC0D", kind="decision", parent="grp_cap"),

        # Left branch from d_unscrew (Yes -> Auto-Tare)
        NodeDef("n_tare", "Auto-Tare Zero Offset", ["zero_offset = 0.8*old + 0.2*median", "Cancels thermal drift"], 60, 705, 240, 75, "#E8F8F5", "#16A085", parent="grp_cap"),

        # Center-right branch from d_unscrew (No -> Inertial Comp + Classify)
        NodeDef("n_comp", "Inertial Mass & Delta Classifier", ["m = Fz / clamp(az, 0.85, 1.15)", "Sip >= +15g | Refill <= -25g"], 390, 705, 360, 75, "#FFFFFF", "#2980B9", parent="grp_cap"),
        NodeDef("n_ring", "Push to 64-Event Ring Buffer", ["Packed 12-byte event <IIhH>", "Advertise BLE 'DrinkLog' (6 s window)"], 390, 825, 360, 78, "#EBF5FB", "#1F618D", parent="grp_cap"),

        # Phone column
        NodeDef("n_scan", "Android BLE GATT Client", ["Connect & Read Status (0004): <IHH>", "Map uptime_s -> Instant"], 890, 200, 320, 95, "#FFFFFF", "#8E44AD", parent="grp_phone"),
        NodeDef("n_notify", "Receive Event Notify (0002)", ["Decode 12-B HydrationEvent", "Filter delta_ml > 0 (ignore refills)"], 890, 390, 320, 95, "#FFFFFF", "#8E44AD", parent="grp_phone"),
        NodeDef("n_hc", "Write Health Connect Record", ["HydrationRecord(Volume.milliliters)", "clientRecordId = drinklog-MAC-seq"], 890, 580, 320, 100, "#EAFAF1", "#27AE60", parent="grp_phone"),
        NodeDef("n_ack", "Send BLE ACK (0003)", ["Write 4-byte uint32 last_acked_seq", "Cap clears ring up to seq"], 890, 770, 320, 90, "#F4ECF7", "#8E44AD", kind="terminator", parent="grp_phone"),
    ]

    edges = [
        EdgeDef("f1", "n_sleep", "n_wake", [(395, 158), (395, 200)], "#2980B9"),
        EdgeDef("f2", "n_wake", "d_still", [(395, 268), (395, 310)], "#2980B9"),
        EdgeDef("f3_no", "d_still", "n_sleep", [(235, 357), (105, 357), (105, 124), (200, 124)], "#C0392B", "No (Timeout)", label_pos=(105, 240)),
        EdgeDef("f3_yes", "d_still", "n_sample", [(395, 405), (395, 455)], "#27AE60", "Yes (Steady)", label_pos=(445, 430)),
        EdgeDef("f4", "n_sample", "d_unscrew", [(395, 531), (395, 575)], "#27AE60"),
        EdgeDef("f5_yes", "d_unscrew", "n_tare", [(255, 619), (180, 619), (180, 705)], "#16A085", "Yes", label_pos=(205, 603)),
        EdgeDef("f5_no", "d_unscrew", "n_comp", [(535, 619), (570, 619), (570, 705)], "#2980B9", "No (Bottle Attached)", label_pos=(615, 603)),
        EdgeDef("f6_loop", "n_tare", "n_sleep", [(60, 742), (48, 742), (48, 112), (200, 112)], "#16A085", "Return", dashed=True, label_pos=(48, 430)),
        EdgeDef("f7", "n_comp", "n_ring", [(570, 780), (570, 825)], "#1F618D", "Sip / Refill", label_pos=(615, 802)),
        EdgeDef("f8_ble", "n_ring", "n_notify", [(750, 864), (822, 864), (822, 437), (890, 437)], "#8E44AD", "BLE Notify", label_pos=(822, 650)),
        EdgeDef("f9_scan", "n_scan", "n_notify", [(1050, 295), (1050, 390)], "#8E44AD", "Subscribe 0002", label_pos=(1105, 342)),
        EdgeDef("f10_hc", "n_notify", "n_hc", [(1050, 485), (1050, 580)], "#27AE60", "Insert Record", label_pos=(1105, 532)),
        EdgeDef("f11_ack", "n_hc", "n_ack", [(1050, 680), (1050, 770)], "#8E44AD", "On Success", label_pos=(1100, 725)),
        EdgeDef("f12_ack_back", "n_ack", "n_ring", [(890, 815), (835, 815), (835, 885), (750, 885)], "#8E44AD", "ACK seq", dashed=True, label_pos=(835, 845)),
    ]

    xml_path = os.path.join(out_dir, "firmware_ble_pipeline.drawio")
    png_path = os.path.join(out_dir, "firmware_ble_pipeline.png")
    write_drawio_xml(xml_path, "DrinkLog_Firmware_BLE_Pipeline", W, H, nodes, edges)
    render_png(
        png_path,
        "DrinkLog End-to-End Firmware DSP, Ring Buffer & Health Connect Pipeline",
        "Auto-Tare on Unscrew + Inertial Mass Compensation (m = Fz/az) + Reliable Idempotent BLE Sync",
        W,
        H,
        nodes,
        edges,
    )


def main() -> None:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    build_circuit_schematic(out_dir)
    build_firmware_pipeline(out_dir)
    print(f"Generated Draw.io & PNG diagrams in: {out_dir}")


if __name__ == "__main__":
    main()
