#!/usr/bin/env python3
"""
Generate 1.1x D_cap proportioned 3D CAD meshes (.stl & color-coded .glb across
pet_30 [33.6 mm], compact_45 [45.1 mm], and universal_65 [69.3 mm]) plus a
4-panel mechanical orthographic blueprint comparing all 4 cap tiers.
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
import trimesh

TIER_SPECS: Dict[str, Tuple[float, float]] = {
    "pet_30":   (30.5, round(30.5 * 1.10, 2)),  # 33.55 mm (~33.6 mm)
    "sport_40": (41.0, round(41.0 * 1.10, 2)),  # 45.10 mm
    "flask_48": (48.0, round(48.0 * 1.10, 2)),  # 52.80 mm
    "wide_63":  (63.0, round(63.0 * 1.10, 2)),  # 69.30 mm
}


def _make_annulus(od: float, id_: float, height: float, z0: float = 0.0, sections: int = 72) -> trimesh.Trimesh:
    r_out, r_in = od / 2.0, id_ / 2.0
    theta = np.linspace(0.0, 2.0 * np.pi, sections, endpoint=False)
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    bo = np.column_stack([r_out * cos_t, r_out * sin_t, np.full(sections, z0)])
    to = np.column_stack([r_out * cos_t, r_out * sin_t, np.full(sections, z0 + height)])
    bi = np.column_stack([r_in * cos_t, r_in * sin_t, np.full(sections, z0)])
    ti = np.column_stack([r_in * cos_t, r_in * sin_t, np.full(sections, z0 + height)])
    verts = np.vstack([bo, to, bi, ti])
    faces = []
    n = sections
    for i in range(n):
        j = (i + 1) % n
        faces.extend([[i, j, n + j], [i, n + j, n + i]])
        faces.extend([[2 * n + i, 3 * n + j, 2 * n + j], [2 * n + i, 3 * n + i, 3 * n + j]])
        faces.extend([[n + i, n + j, 3 * n + j], [n + i, 3 * n + j, 3 * n + i]])
        faces.extend([[i, 2 * n + j, j], [i, 2 * n + i, 2 * n + j]])
    mesh = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=True)
    trimesh.repair.fix_normals(mesh)
    return mesh


def _make_half_arc_annulus(od: float, id_: float, height: float, z0: float, sections: int = 36) -> trimesh.Trimesh:
    r_out, r_in = od / 2.0, id_ / 2.0
    theta = np.linspace(-np.pi / 2, np.pi / 2, sections + 1)
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    m = len(theta)
    bo = np.column_stack([r_out * cos_t, r_out * sin_t, np.full(m, z0)])
    to = np.column_stack([r_out * cos_t, r_out * sin_t, np.full(m, z0 + height)])
    bi = np.column_stack([r_in * cos_t, r_in * sin_t, np.full(m, z0)])
    ti = np.column_stack([r_in * cos_t, r_in * sin_t, np.full(m, z0 + height)])
    verts = np.vstack([bo, to, bi, ti])
    faces = []
    for i in range(m - 1):
        j = i + 1
        faces.extend([[i, j, m + j], [i, m + j, m + i]])
        faces.extend([[2 * m + i, 3 * m + j, 2 * m + j], [2 * m + i, 3 * m + i, 3 * m + j]])
        faces.extend([[m + i, m + j, 3 * m + j], [m + i, 3 * m + j, 3 * m + i]])
        faces.extend([[i, 2 * m + j, j], [i, 2 * m + i, 2 * m + j]])
    faces.extend([[0, m, 3 * m], [0, 3 * m, 2 * m]])
    e = m - 1
    faces.extend([[e, 2 * m + e, 3 * m + e], [e, 3 * m + e, m + e]])
    mesh = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=True)
    trimesh.repair.fix_normals(mesh)
    return mesh


def _colorize(mesh: trimesh.Trimesh, rgba: Tuple[int, int, int, int]) -> trimesh.Trimesh:
    m = mesh.copy()
    m.visual.face_colors = np.tile(np.array(rgba, dtype=np.uint8), (len(m.faces), 1))
    return m


def build_cap_assembly(tier: str = "pet_30") -> Tuple[trimesh.Scene, trimesh.Trimesh]:
    cap_od, puck_od = TIER_SPECS[tier]
    chuck_h = 5.2
    parts: List[Tuple[str, trimesh.Trimesh]] = []

    # 1. Outer 1.1x D_cap compression collar + knurl ribs
    collar = _make_annulus(puck_od, cap_od + 0.6, chuck_h, z0=0.0)
    parts.append(("compression_collar", _colorize(collar, (52, 73, 94, 255))))
    for k in range(36):
        ang = np.deg2rad(k * 10.0)
        rib = trimesh.creation.box([0.55, 1.2, chuck_h - 0.8])
        rib.apply_translation([puck_od / 2.0 - 0.05, 0.0, chuck_h / 2.0])
        rib.apply_transform(trimesh.transformations.rotation_matrix(ang, [0, 0, 1]))
        parts.append((f"rib_{k}", _colorize(rib, (44, 62, 80, 255))))

    # 2. 6-petal compliant TPU/silicone grip collet
    for k in range(6):
        ang = np.deg2rad(k * 60.0)
        rot = trimesh.transformations.rotation_matrix(ang, [0, 0, 1])
        pad = trimesh.creation.box([1.3, 8.0, chuck_h - 0.8])
        pad.apply_translation([cap_od / 2.0 + 0.1, 0.0, chuck_h / 2.0])
        pad.apply_transform(rot)
        parts.append((f"collet_petal_{k}", _colorize(pad, (230, 126, 34, 255))))

    # 3. Chuck hub plate (z=5.2..7.0)
    hub_od = min(puck_od - 1.0, 32.0 if tier == "pet_30" else puck_od - 4.0)
    hub = trimesh.creation.cylinder(radius=hub_od / 2.0, height=1.8, sections=64)
    hub.apply_translation([0, 0, chuck_h + 0.9])
    parts.append(("chuck_hub", _colorize(hub, (93, 109, 126, 255))))

    # 4. Universal Ø30.0 mm x 0.8 mm 3-spoke stainless flexure (z=7.0..7.8)
    z_flex = chuck_h + 1.8
    flex_out = _make_annulus(30.0, 24.0, 0.8, z0=z_flex)
    flex_in = trimesh.creation.cylinder(radius=5.5, height=0.8, sections=48)
    flex_in.apply_translation([0, 0, z_flex + 0.4])
    parts.append(("flexure_outer_ring", _colorize(flex_out, (189, 195, 199, 255))))
    parts.append(("flexure_inner_boss", _colorize(flex_in, (189, 195, 199, 255))))
    for k in range(3):
        ang = np.deg2rad(k * 120.0)
        rot = trimesh.transformations.rotation_matrix(ang, [0, 0, 1])
        spoke = trimesh.creation.box([8.0, 4.2, 0.8])
        spoke.apply_translation([9.0, 0, z_flex + 0.4])
        spoke.apply_transform(rot)
        parts.append((f"flexure_spoke_{k}", _colorize(spoke, (171, 178, 185, 255))))
        if k < 2:
            sg = trimesh.creation.box([4.2, 2.8, 0.15])
            sg.apply_translation([9.0, 0, z_flex + 0.85])
            sg.apply_transform(rot)
            parts.append((f"strain_gauge_{k}", _colorize(sg, (212, 172, 13, 255))))

    # 5. Upper puck shell + 401520 LiPo + Ø28.0 mm V2.1 PCB + IPX8 USB-C plug
    z_puck = z_flex + 0.8 + 0.35
    puck_ring = _make_annulus(puck_od, 29.2, 5.6, z0=z_puck)
    puck_floor = trimesh.creation.cylinder(radius=puck_od / 2.0, height=1.0, sections=64)
    puck_floor.apply_translation([0, 0, z_puck + 0.5])
    parts.append(("puck_shell_wall", _colorize(puck_ring, (31, 97, 141, 255))))
    parts.append(("puck_shell_floor", _colorize(puck_floor, (31, 97, 141, 255))))

    lipo = trimesh.creation.box([20.0, 15.0, 3.8])
    lipo.apply_translation([0, 0, z_puck + 2.9])
    parts.append(("lipo_401520", _colorize(lipo, (243, 156, 18, 255))))

    pcb = trimesh.creation.cylinder(radius=14.0, height=0.8, sections=48)
    pcb.apply_translation([0, 0, z_puck + 5.2])
    parts.append(("pcb_28mm", _colorize(pcb, (14, 98, 81, 255))))

    usb_plug = trimesh.creation.box([9.0, 2.4, 3.4])
    usb_plug.apply_translation([0, -puck_od / 2.0 - 0.3, z_puck + 3.4])
    parts.append(("usbc_tpu_plug", _colorize(usb_plug, (231, 76, 60, 255))))

    # 6. Top lid + flush folding finger bail
    z_lid = z_puck + 5.6
    lid = trimesh.creation.cylinder(radius=(puck_od - 4.4) / 2.0, height=2.0, sections=64)
    lid.apply_translation([0, 0, z_lid + 1.0])
    lid_skirt = _make_annulus(puck_od, puck_od - 4.4, 0.8, z0=z_lid)
    parts.append(("top_lid", _colorize(lid, (41, 128, 185, 255))))
    parts.append(("top_lid_skirt", _colorize(lid_skirt, (41, 128, 185, 255))))

    bail = _make_half_arc_annulus(puck_od - 0.3, puck_od - 4.0, 1.2, z0=z_lid + 0.8)
    parts.append(("folding_bail", _colorize(bail, (208, 211, 212, 255))))

    scene = trimesh.Scene()
    for name, m in parts:
        scene.add_geometry(m, node_name=name, geom_name=name)
    combined = trimesh.util.concatenate([m for _, m in parts])
    return scene, combined


def render_orthographic_views(out_png: str, mesh_pet: trimesh.Trimesh) -> None:
    fig = plt.figure(figsize=(15.5, 11.5), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    fig.suptitle(
        "DrinkLog 1.1x D_cap Proportioned Architecture — Universal Ø28 mm Core Across 4 Standard Bottle Cap Tiers",
        fontsize=13.5, fontweight="bold", color="#1A252C", y=0.975
    )

    # Panel A: Sleek 1.1x D_cap Cross-Section (33.6 mm on 30.5 mm PET Cap)
    axA = fig.add_subplot(2, 2, 1)
    axA.set_title("A. Sleek pet_30 Cross-Section (Ø33.6 mm = 1.10 × 30.5 mm Cap)",
                  fontsize=10.2, fontweight="bold", color="#1B4F72", pad=8)
    axA.set_xlim(-30, 30)
    axA.set_ylim(-14, 24)
    axA.set_aspect("equal")
    axA.axis("off")

    axA.add_patch(Rectangle((-15.25, -12), 30.5, 16.5, facecolor="#D6EAF8", edgecolor="#5DADE2", lw=1.3, ls="--"))
    axA.text(0, -6.5, "Standard PET Cap\n(Ø30.5 mm OD)", ha="center", va="center", fontsize=8, color="#21618C", fontweight="bold")

    # Tapered 33.6 mm compression sleeve + orange TPU split collet (1.55 mm wall/side!)
    axA.add_patch(Rectangle((-16.8, 0), 1.55, 5.2, facecolor="#34495E", edgecolor="#1B2631"))
    axA.add_patch(Rectangle((15.25, 0), 1.55, 5.2, facecolor="#34495E", edgecolor="#1B2631"))
    axA.add_patch(Rectangle((-15.7, 0.5), 1.0, 4.2, facecolor="#E67E22", edgecolor="none"))
    axA.add_patch(Rectangle((14.7, 0.5), 1.0, 4.2, facecolor="#E67E22", edgecolor="none"))

    # Hub + Ø30.0 mm 301-SS Flexure
    axA.add_patch(Rectangle((-16.0, 5.2), 32.0, 1.8, facecolor="#5D6D7E", edgecolor="#1B2631"))
    axA.add_patch(Rectangle((-15.0, 7.0), 30.0, 0.8, facecolor="#BDC3C7", edgecolor="#566573"))
    axA.add_patch(Rectangle((-11.0, 7.8), 4.5, 0.25, facecolor="#D4AC0D", edgecolor="none"))
    axA.add_patch(Rectangle((6.5, 7.8), 4.5, 0.25, facecolor="#D4AC0D", edgecolor="none"))

    # Upper puck (Ø33.6 mm) + 401520 LiPo + Ø28 mm PCB + IPX8 USB-C
    axA.add_patch(Rectangle((-16.8, 8.15), 33.6, 5.6, facecolor="#1F618D", edgecolor="#154360"))
    axA.add_patch(Rectangle((-14.6, 9.15), 29.2, 4.6, facecolor="#F8F9F9", edgecolor="#154360", lw=0.8))
    axA.add_patch(Rectangle((-10.0, 9.25), 20.0, 3.6, facecolor="#F39C12", edgecolor="#B9770E"))
    axA.text(0, 11.05, "401520 LiPo (100mAh)", ha="center", va="center", fontsize=6.5, fontweight="bold", color="#FFFFFF")
    axA.add_patch(Rectangle((-14.0, 12.95), 28.0, 0.8, facecolor="#0E6251", edgecolor="#145A32"))
    axA.add_patch(Rectangle((-15.2, 13.75), 30.4, 2.0, facecolor="#2980B9", edgecolor="#1B4F72"))
    axA.add_patch(Rectangle((-16.7, 14.55), 1.8, 1.2, facecolor="#D0D3D4", edgecolor="#566573"))
    axA.add_patch(Rectangle((14.9, 14.55), 1.8, 1.2, facecolor="#D0D3D4", edgecolor="#566573"))
    axA.add_patch(Rectangle((-17.6, 9.8), 3.6, 2.8, facecolor="#E74C3C", edgecolor="#922B21"))
    axA.text(-15.8, 11.2, "USB-C", ha="center", va="center", fontsize=4.8, fontweight="bold", color="#FFFFFF")

    axA.annotate("Flush Bail (100% Weight)", xy=(16.0, 15.2), xytext=(9.0, 20.5),
                 fontsize=7.5, fontweight="bold", color="#1B2631",
                 arrowprops=dict(arrowstyle="->", color="#1B2631", lw=1.0))
    axA.annotate("Universal Ø30 mm Flexure", xy=(-13.5, 7.4), xytext=(-29.0, 19.2),
                 fontsize=7.5, fontweight="bold", color="#7D6608",
                 arrowprops=dict(arrowstyle="->", color="#7D6608", lw=1.0))
    axA.annotate("IPX8 USB-C + TPU Plug", xy=(-17.6, 11.0), xytext=(-29.5, -2.5),
                 fontsize=7.0, color="#922B21", fontweight="bold",
                 arrowprops=dict(arrowstyle="->", color="#922B21", lw=1.0))
    axA.annotate("1.1x Tapered Grip (1.55mm)", xy=(-15.5, 2.2), xytext=(-29.5, -10.5),
                 fontsize=7.2, color="#D35400", fontweight="bold",
                 arrowprops=dict(arrowstyle="->", color="#D35400", lw=1.0))
    axA.annotate("Ø28 mm PCBWay V2.1 Core", xy=(11.0, 13.3), xytext=(8.5, -10.5),
                 fontsize=7.2, color="#145A32", fontweight="bold",
                 arrowprops=dict(arrowstyle="->", color="#145A32", lw=1.0))

    # Panel B: Universal Ø30.0 mm 3-Spoke Stainless Flexure (fits ALL 4 shells)
    axB = fig.add_subplot(2, 2, 2)
    axB.set_title("B. Universal Ø30.0 mm 3-Spoke 301-SS Flexure (Fits All Tiers)",
                  fontsize=10.2, fontweight="bold", color="#145A32", pad=8)
    axB.set_xlim(-22, 22)
    axB.set_ylim(-22, 22)
    axB.set_aspect("equal")
    axB.axis("off")

    axB.add_patch(Circle((0, 0), 15.0, facecolor="#EAFAF1", edgecolor="#27AE60", lw=1.5))
    axB.add_patch(Circle((0, 0), 12.0, facecolor="#FFFFFF", edgecolor="#7F8C8D", lw=1.0))
    axB.add_patch(Circle((0, 0), 5.5, facecolor="#BDC3C7", edgecolor="#566573", lw=1.5))
    for idx, deg in enumerate([90, 210, 330]):
        rad = np.deg2rad(deg)
        c, s = np.cos(rad), np.sin(rad)
        rot_m = np.array([[c, -s], [s, c]])
        rc = np.array([[5.0, -2.1], [12.8, -2.1], [12.8, 2.1], [5.0, 2.1]]) @ rot_m.T
        axB.add_patch(Polygon(rc, closed=True, facecolor="#BDC3C7", edgecolor="#566573", lw=1.1))
        if idx < 2:
            sg = np.array([[6.8, -1.3], [11.0, -1.3], [11.0, 1.3], [6.8, 1.3]]) @ rot_m.T
            axB.add_patch(Polygon(sg, closed=True, facecolor="#F1C40F", edgecolor="#9A7D0A", lw=1.1))
            axB.text(8.9 * c, 8.9 * s, "1kΩ", ha="center", va="center", fontsize=6.5, fontweight="bold")
    axB.text(0, 0, "Inner\nHub", ha="center", va="center", fontsize=7.5, fontweight="bold", color="#1B2631")
    axB.text(0, -18.5, "Shared Ø30.0 mm Laser-Cut Flexure + Ø28.0 mm PCB Core",
             ha="center", va="center", fontsize=8, color="#145A32", fontweight="bold")

    # Panel C: 4-Tier 1.1x D_cap Shell Scaling Comparison Plan
    axC = fig.add_subplot(2, 2, 3)
    axC.set_title("C. 4-Tier 1.10 × D_cap Shell Comparison (Zero Mushroom Overhang)",
                  fontsize=10.2, fontweight="bold", color="#2C3E50", pad=8)
    axC.set_xlim(-42, 42)
    axC.set_ylim(-42, 42)
    axC.set_aspect("equal")
    axC.axis("off")

    tiers_vis = [
        ("wide_63: 63 -> 69.3mm", 69.3 / 2.0, "#EAECEE", "#5D6D7E", 31.5),
        ("flask_48: 48 -> 52.8mm", 52.8 / 2.0, "#D6EAF8", "#2980B9", 23.0),
        ("sport_40: 41 -> 45.1mm", 45.1 / 2.0, "#D5F5E3", "#27AE60", 18.8),
        ("pet_30: 30.5 -> 33.6mm", 33.6 / 2.0, "#FCF3CF", "#D4AC0D", 14.5),
    ]
    for lbl, r_puck, fc, ec, ty in tiers_vis:
        axC.add_patch(Circle((0, 0), r_puck, facecolor=fc, edgecolor=ec, lw=1.8))
        axC.text(0, ty, lbl, ha="center", va="center", fontsize=6.8, fontweight="bold", color="#1B2631")
    axC.add_patch(Circle((0, 0), 14.0, facecolor="#0E6251", edgecolor="#F1C40F", lw=1.5, ls="--"))
    axC.text(0, 0, "Universal\nØ28 mm PCB\nCore", ha="center", va="center", fontsize=7.0, fontweight="bold", color="#FFFFFF")

    # Panel D: 3D Shaded Sleek pet_30 Assembly
    axD = fig.add_subplot(2, 2, 4, projection="3d")
    axD.set_title("D. 3D Sleek pet_30 Puck Mesh (Ø33.6 mm = 1.10 × D_cap)",
                  fontsize=10.2, fontweight="bold", color="#1B4F72", pad=8)
    tris = mesh_pet.vertices[mesh_pet.faces]
    cols = mesh_pet.visual.face_colors[:, :3] / 255.0
    pc = Poly3DCollection(tris, facecolors=cols, edgecolor=(0.12, 0.12, 0.12, 0.08), linewidth=0.15)
    axD.add_collection3d(pc)
    axD.set_xlim(-20, 20)
    axD.set_ylim(-20, 20)
    axD.set_zlim(-2, 18)
    axD.view_init(elev=28, azim=38)
    axD.set_xlabel("X (mm)", fontsize=8)
    axD.set_ylabel("Y (mm)", fontsize=8)
    axD.set_zlabel("Z (mm)", fontsize=8)
    axD.tick_params(labelsize=7)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="#FFFFFF")
    plt.close(fig)


def main() -> None:
    cad_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(cad_dir, "outputs")
    os.makedirs(out_dir, exist_ok=True)

    scene_pet, mesh_pet = build_cap_assembly("pet_30")
    scene_sport, mesh_sport = build_cap_assembly("sport_40")
    scene_wide, mesh_wide = build_cap_assembly("wide_63")

    # Export explicit 1.1x named meshes AND updated standard filenames
    mesh_pet.export(os.path.join(out_dir, "cap_gripper_pet_30_1p1x.stl"))
    scene_pet.export(os.path.join(out_dir, "cap_gripper_pet_30_1p1x.glb"))
    scene_wide.export(os.path.join(out_dir, "cap_gripper_wide_63_1p1x.glb"))

    mesh_wide.export(os.path.join(out_dir, "cap_gripper_universal_65.stl"))
    scene_wide.export(os.path.join(out_dir, "cap_gripper_universal_65.glb"))
    scene_sport.export(os.path.join(out_dir, "cap_gripper_compact_45.glb"))

    render_orthographic_views(os.path.join(out_dir, "mechanical_orthographic_views.png"), mesh_pet)
    for lbl, m in [("pet_30_1p1x", mesh_pet), ("sport_40_1p1x", mesh_sport), ("wide_63_1p1x", mesh_wide)]:
        dims = m.bounds[1] - m.bounds[0]
        print(f"[{lbl}] triangles={len(m.faces)}, bounds_mm=({dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f})")


if __name__ == "__main__":
    main()
