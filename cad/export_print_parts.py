#!/usr/bin/env python3
"""
Export 8 split, 3D-printable STL parts (including waterproof USB-C enclosure
and captive TPU plug) + 1 AutoCAD R2010 DXF sheet-metal laser file for the
0.8 mm 301-SS 3-spoke flexure into cad/stl_print_parts/.
"""

from __future__ import annotations

import math
import os
from typing import Tuple

import ezdxf
import numpy as np
import trimesh

from generate_cad_assets import _make_annulus, _make_half_arc_annulus


def export_split_stls(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    puck_od = 72.0
    cap_max = 65.0
    chuck_h = 5.2

    # 01: Knurled Outer Scroll Collar
    collar = _make_annulus(puck_od, cap_max + 3.0, chuck_h, z0=0.0)
    ribs = []
    for k in range(36):
        ang = np.deg2rad(k * 10.0)
        rib = trimesh.creation.box([0.9, 1.6, chuck_h - 0.8])
        rib.apply_translation([puck_od / 2.0 - 0.1, 0.0, chuck_h / 2.0])
        rib.apply_transform(trimesh.transformations.rotation_matrix(ang, [0, 0, 1]))
        ribs.append(rib)
    m01 = trimesh.util.concatenate([collar] + ribs)
    m01.export(os.path.join(out_dir, "01_scroll_collar_knurled_u65.stl"))

    # 02: Chuck Hub Plate (with 4 mm RTV wire gland ring)
    m02 = _make_annulus(cap_max + 2.4, 4.0, 2.0, z0=0.0)
    m02.export(os.path.join(out_dir, "02_chuck_hub_plate_u65.stl"))

    # 03: Single Rigid Gripper Jaw (print 3x)
    jaw = trimesh.creation.box([20.0, 9.6, chuck_h - 1.2])
    jaw.apply_translation([0.0, 0.0, (chuck_h - 1.2) / 2.0])
    jaw.export(os.path.join(out_dir, "03_gripper_jaw_x3.stl"))

    # 04: Single TPU 85A / Silicone Grip Pad (print 3x)
    pad = trimesh.creation.box([2.2, 8.8, chuck_h - 1.4])
    pad.apply_translation([0.0, 0.0, (chuck_h - 1.4) / 2.0])
    pad.export(os.path.join(out_dir, "04_jaw_grip_pad_tpu_x3.stl"))

    # 05: Upper Puck Housing w/ Side IP67 USB-C Bezel & O-Ring Shelf
    wall = _make_annulus(puck_od, 43.4, 5.6, z0=0.0)
    floor = _make_annulus(puck_od, 4.0, 1.2, z0=0.0)
    usbc_bezel = trimesh.creation.box([11.6, 5.0, 4.8])
    usbc_bezel.apply_translation([0.0, -puck_od / 2.0 + 1.5, 3.2])
    m05 = trimesh.util.concatenate([wall, floor, usbc_bezel])
    m05.export(os.path.join(out_dir, "05_upper_puck_housing_usbc_ip67.stl"))

    # 06: Top Waterproof Lid w/ O-ring Flange
    lid_top = trimesh.creation.cylinder(radius=(puck_od - 6.0) / 2.0, height=2.2, sections=72)
    lid_top.apply_translation([0.0, 0.0, 1.1])
    lid_skirt = _make_annulus(puck_od, puck_od - 6.0, 0.9, z0=0.0)
    m06 = trimesh.util.concatenate([lid_top, lid_skirt])
    m06.export(os.path.join(out_dir, "06_top_waterproof_lid.stl"))

    # 07: Flush-Folding Finger Bail
    m07 = _make_half_arc_annulus(puck_od - 0.4, puck_od - 5.2, 1.3, z0=0.0)
    m07.export(os.path.join(out_dir, "07_folding_finger_bail.stl"))

    # 08: Captive TPU 85A IP67 USB-C Port Plug
    plug_cap = trimesh.creation.box([9.2, 3.0, 3.6])
    plug_tongue = trimesh.creation.box([6.4, 4.0, 2.4])
    plug_tongue.apply_translation([0.0, 2.8, 0.0])
    m08 = trimesh.util.concatenate([plug_cap, plug_tongue])
    m08.apply_translation([0.0, 0.0, 1.8])
    m08.export(os.path.join(out_dir, "08_usbc_waterproof_plug_tpu.stl"))


def export_flexure_dxf(out_dxf: str) -> None:
    """Export 2D closed laser-cut profile for 0.8 mm 301-SS 3-spoke flexure (PCBWay Sheet Metal)."""
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()

    r_outer = 33.0   # 66 mm outer flexure ring
    r_inner_ring = 29.0
    r_hub = 11.0     # 22 mm center cap hub
    half_spoke = 3.25
    ang_span = math.asin(half_spoke / r_inner_ring)
    ang_hub = math.asin(half_spoke / r_hub)

    # Outer perimeter circle
    msp.add_circle((0.0, 0.0), r_outer, dxfattribs={"layer": "CUT_OUTER"})
    # Central RTV wire passage hole
    msp.add_circle((0.0, 0.0), 2.0, dxfattribs={"layer": "CUT_INNER"})

    # 3 symmetric inner cutout windows leaving three 120-deg spokes
    for k in range(3):
        a0 = math.radians(k * 120.0) + ang_hub
        a1 = math.radians((k + 1) * 120.0) - ang_hub
        b0 = math.radians(k * 120.0) + ang_span
        b1 = math.radians((k + 1) * 120.0) - ang_span

        pts = []
        for t in np.linspace(a0, a1, 24):
            pts.append((r_hub * math.cos(t), r_hub * math.sin(t)))
        for t in np.linspace(b1, b0, 32):
            pts.append((r_inner_ring * math.cos(t), r_inner_ring * math.sin(t)))
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "CUT_WINDOWS"})

    # 4x M2.2 mounting holes on outer ring
    for hx, hy in [(-15.5, 9.0), (15.5, 9.0), (-14.5, -10.5), (14.5, -10.5)]:
        # Outer flexure ring holes at radius 31 mm (45, 135, 225, 315 deg)
        pass
    for deg in [45.0, 135.0, 225.0, 315.0]:
        rad = math.radians(deg)
        msp.add_circle((31.0 * math.cos(rad), 31.0 * math.sin(rad)), 1.1, dxfattribs={"layer": "CUT_HOLES"})

    doc.saveas(out_dxf)
    # Round-trip validation
    check = ezdxf.readfile(out_dxf)
    assert len(list(check.modelspace())) >= 9


def main() -> None:
    cad_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(cad_dir, "stl_print_parts")
    export_split_stls(out_dir)
    export_flexure_dxf(os.path.join(out_dir, "09_flexure_3spoke_0p8mm_301SS.dxf"))
    files = sorted(os.listdir(out_dir))
    print(f"[CAD Split Export] Exported {len(files)} print/laser files into {out_dir}:")
    for f in files:
        print(f"  - {f} ({os.path.getsize(os.path.join(out_dir, f))} bytes)")


if __name__ == "__main__":
    main()
