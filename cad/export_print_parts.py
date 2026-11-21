#!/usr/bin/env python3
"""
Export 8 split, 3D-printable STL parts for the sleek 1.1x D_cap hero shell
(pet_30: Ø33.6 mm OD for 30.5 mm PET caps) + 1 universal Ø30.0 mm laser-cut
0.8 mm 301-SS 3-spoke flexure DXF (fits ALL 4 shell tiers).
"""

from __future__ import annotations

import math
import os

import ezdxf
import numpy as np
import trimesh

from generate_cad_assets import TIER_SPECS, _make_annulus, _make_half_arc_annulus


def export_split_stls(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    cap_od, puck_od = TIER_SPECS["pet_30"]  # 30.5 mm -> 33.55 mm (~33.6 mm)
    chuck_h = 5.2

    # 01: Knurled 1.1x Compression Collar (Ø33.6 mm)
    collar = _make_annulus(puck_od, cap_od + 0.6, chuck_h, z0=0.0)
    ribs = []
    for k in range(36):
        ang = np.deg2rad(k * 10.0)
        rib = trimesh.creation.box([0.55, 1.2, chuck_h - 0.8])
        rib.apply_translation([puck_od / 2.0 - 0.05, 0.0, chuck_h / 2.0])
        rib.apply_transform(trimesh.transformations.rotation_matrix(ang, [0, 0, 1]))
        ribs.append(rib)
    trimesh.util.concatenate([collar] + ribs).export(os.path.join(out_dir, "01_scroll_collar_knurled_u65.stl"))

    # 02: Inner Flexure Carrier Hub Plate (Ø32 mm w/ 3.6 mm RTV wire gland)
    _make_annulus(32.0, 3.6, 1.8, z0=0.0).export(os.path.join(out_dir, "02_chuck_hub_plate_u65.stl"))

    # 03: Locking Wedge Insert (x3)
    jaw = trimesh.creation.box([2.2, 6.0, chuck_h - 1.2])
    jaw.apply_translation([0.0, 0.0, (chuck_h - 1.2) / 2.0])
    jaw.export(os.path.join(out_dir, "03_gripper_jaw_x3.stl"))

    # 04: Compliant TPU 85A Split Grip Collet Petals (6-petal ring)
    petals = []
    for k in range(6):
        ang = np.deg2rad(k * 60.0)
        p = trimesh.creation.box([1.3, 8.0, chuck_h - 0.8])
        p.apply_translation([cap_od / 2.0 + 0.1, 0.0, chuck_h / 2.0])
        p.apply_transform(trimesh.transformations.rotation_matrix(ang, [0, 0, 1]))
        petals.append(p)
    trimesh.util.concatenate(petals).export(os.path.join(out_dir, "04_jaw_grip_pad_tpu_x3.stl"))

    # 05: Upper Puck Housing w/ Side IP67 USB-C Bezel (Ø33.6 mm housing around Ø28 mm PCB)
    wall = _make_annulus(puck_od, 29.2, 5.6, z0=0.0)
    floor = _make_annulus(puck_od, 3.6, 1.0, z0=0.0)
    usbc_bezel = trimesh.creation.box([11.0, 4.0, 4.6])
    usbc_bezel.apply_translation([0.0, -puck_od / 2.0 + 1.0, 3.2])
    trimesh.util.concatenate([wall, floor, usbc_bezel]).export(os.path.join(out_dir, "05_upper_puck_housing_usbc_ip67.stl"))

    # 06: Top Waterproof Lid
    lid_top = trimesh.creation.cylinder(radius=(puck_od - 4.4) / 2.0, height=2.0, sections=72)
    lid_top.apply_translation([0.0, 0.0, 1.0])
    lid_skirt = _make_annulus(puck_od, puck_od - 4.4, 0.8, z0=0.0)
    trimesh.util.concatenate([lid_top, lid_skirt]).export(os.path.join(out_dir, "06_top_waterproof_lid.stl"))

    # 07: Flush-Folding Finger Bail (Ø33.2 mm)
    _make_half_arc_annulus(puck_od - 0.3, puck_od - 4.0, 1.2, z0=0.0).export(os.path.join(out_dir, "07_folding_finger_bail.stl"))

    # 08: Captive TPU 85A IP67 USB-C Port Plug
    plug_cap = trimesh.creation.box([9.0, 2.4, 3.4])
    plug_tongue = trimesh.creation.box([6.4, 3.5, 2.4])
    plug_tongue.apply_translation([0.0, 2.4, 0.0])
    m08 = trimesh.util.concatenate([plug_cap, plug_tongue])
    m08.apply_translation([0.0, 0.0, 1.7])
    m08.export(os.path.join(out_dir, "08_usbc_waterproof_plug_tpu.stl"))


def export_flexure_dxf(out_dxf: str) -> None:
    """Export universal Ø30.0 mm x 0.8 mm 301-SS 3-spoke flexure DXF (fits all 4 shell tiers)."""
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()

    r_outer = 15.0        # Ø30.0 mm outer ring
    r_inner_ring = 12.0   # Ø24.0 mm inner ring rim
    r_hub = 5.5           # Ø11.0 mm center boss
    half_spoke = 2.1      # 4.2 mm spoke width
    ang_span = math.asin(half_spoke / r_inner_ring)
    ang_hub = math.asin(half_spoke / r_hub)

    msp.add_circle((0.0, 0.0), r_outer, dxfattribs={"layer": "CUT_OUTER"})
    msp.add_circle((0.0, 0.0), 1.8, dxfattribs={"layer": "CUT_INNER"})

    for k in range(3):
        a0 = math.radians(k * 120.0) + ang_hub
        a1 = math.radians((k + 1) * 120.0) - ang_hub
        b0 = math.radians(k * 120.0) + ang_span
        b1 = math.radians((k + 1) * 120.0) - ang_span
        pts = [(r_hub * math.cos(t), r_hub * math.sin(t)) for t in np.linspace(a0, a1, 24)]
        pts += [(r_inner_ring * math.cos(t), r_inner_ring * math.sin(t)) for t in np.linspace(b1, b0, 32)]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "CUT_WINDOWS"})

    # 4x M1.6 mounting holes matching Ø28 mm PCB at 45/135/225/315 deg on r=13.5 mm
    for deg in [45.0, 135.0, 225.0, 315.0]:
        rad = math.radians(deg)
        msp.add_circle((13.5 * math.cos(rad), 13.5 * math.sin(rad)), 0.8, dxfattribs={"layer": "CUT_HOLES"})

    doc.saveas(out_dxf)
    check = ezdxf.readfile(out_dxf)
    assert len(list(check.modelspace())) >= 9


def main() -> None:
    cad_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(cad_dir, "stl_print_parts")
    export_split_stls(out_dir)
    export_flexure_dxf(os.path.join(out_dir, "09_flexure_3spoke_0p8mm_301SS.dxf"))
    for f in sorted(os.listdir(out_dir)):
        print(f"  - {f} ({os.path.getsize(os.path.join(out_dir, f))} bytes)")


if __name__ == "__main__":
    main()
