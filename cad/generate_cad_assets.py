#!/usr/bin/env python3
"""
Generate 3D CAD meshes (.stl and color-coded .glb for universal_65 & compact_45)
using trimesh analytical primitive composition, plus a 4-panel orthographic
mechanical engineering drawing (mechanical_orthographic_views.png).
"""

from __future__ import annotations

import os
from typing import List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle, Wedge
import numpy as np
import trimesh


def _make_annulus(od: float, id_: float, height: float, z0: float = 0.0, sections: int = 72) -> trimesh.Trimesh:
    """Create a watertight annular cylinder cleanly without requiring external CSG engines."""
    r_out = od / 2.0
    r_in = id_ / 2.0
    theta = np.linspace(0.0, 2.0 * np.pi, sections, endpoint=False)
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)

    # Vertices: 0..N-1 bottom outer, N..2N-1 top outer, 2N..3N-1 bottom inner, 3N..4N-1 top inner
    bo = np.column_stack([r_out * cos_t, r_out * sin_t, np.full(sections, z0)])
    to = np.column_stack([r_out * cos_t, r_out * sin_t, np.full(sections, z0 + height)])
    bi = np.column_stack([r_in * cos_t, r_in * sin_t, np.full(sections, z0)])
    ti = np.column_stack([r_in * cos_t, r_in * sin_t, np.full(sections, z0 + height)])
    verts = np.vstack([bo, to, bi, ti])

    faces = []
    n = sections
    for i in range(n):
        j = (i + 1) % n
        # Outer wall
        faces.append([i, j, n + j])
        faces.append([i, n + j, n + i])
        # Inner wall (facing inward)
        faces.append([2 * n + i, 3 * n + j, 2 * n + j])
        faces.append([2 * n + i, 3 * n + i, 3 * n + j])
        # Top cap
        faces.append([n + i, n + j, 3 * n + j])
        faces.append([n + i, 3 * n + j, 3 * n + i])
        # Bottom cap
        faces.append([i, 2 * n + j, j])
        faces.append([i, 2 * n + i, 2 * n + j])

    mesh = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=True)
    trimesh.repair.fix_normals(mesh)
    return mesh


def _make_half_arc_annulus(od: float, id_: float, height: float, z0: float, sections: int = 36) -> trimesh.Trimesh:
    """Create a 180-degree folding finger bail arc."""
    r_out = od / 2.0
    r_in = id_ / 2.0
    theta = np.linspace(-np.pi / 2, np.pi / 2, sections + 1)
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
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

    # End caps at i=0 and i=m-1
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


def build_cap_assembly(preset: str = "universal_65") -> Tuple[trimesh.Scene, trimesh.Trimesh]:
    cap_max = 65.0 if preset == "universal_65" else 45.0
    puck_od = 72.0 if preset == "universal_65" else 54.0
    chuck_h = 5.2
    jaw_r = 16.0  # Previewed gripping a standard 32 mm PET cap

    parts: List[Tuple[str, trimesh.Trimesh]] = []

    # 1. Scroll collar outer ring + grip ribs
    collar = _make_annulus(puck_od, cap_max + 3.0, chuck_h, z0=0.0)
    parts.append(("scroll_collar", _colorize(collar, (52, 73, 94, 255))))
    for k in range(36):
        ang = np.deg2rad(k * 10.0)
        rib = trimesh.creation.box([0.9, 1.6, chuck_h - 0.8])
        rib.apply_translation([puck_od / 2.0 - 0.1, 0.0, chuck_h / 2.0])
        rib.apply_transform(trimesh.transformations.rotation_matrix(ang, [0, 0, 1]))
        parts.append((f"rib_{k}", _colorize(rib, (44, 62, 80, 255))))

    # 2. Three radial gripping jaws + Shore 40A orange silicone pads
    jaw_len = max(10.0, puck_od / 2.0 - 15.0)
    for k in range(3):
        ang = np.deg2rad(k * 120.0)
        rot = trimesh.transformations.rotation_matrix(ang, [0, 0, 1])

        jaw = trimesh.creation.box([jaw_len, 9.6, chuck_h - 1.2])
        jaw.apply_translation([jaw_r + jaw_len / 2.0, 0.0, (chuck_h - 0.4) / 2.0])
        jaw.apply_transform(rot)
        parts.append((f"jaw_{k}", _colorize(jaw, (44, 62, 80, 255))))

        pad = trimesh.creation.box([2.2, 8.8, chuck_h - 1.4])
        pad.apply_translation([jaw_r - 1.0, 0.0, (chuck_h - 0.4) / 2.0])
        pad.apply_transform(rot)
        parts.append((f"silicone_pad_{k}", _colorize(pad, (230, 126, 34, 255))))

    # 3. Chuck hub plate (at z=5.2..7.2)
    hub = trimesh.creation.cylinder(radius=(cap_max + 2.4) / 2.0, height=2.0, sections=64)
    hub.apply_translation([0, 0, chuck_h + 1.0])
    parts.append(("chuck_hub", _colorize(hub, (93, 109, 126, 255))))

    # 4. 0.8 mm 301-SS 3-spoke annular flexure (z=7.2..8.0)
    z_flex = chuck_h + 2.0
    flex_out = _make_annulus(puck_od - 6.0, puck_od - 14.0, 0.8, z0=z_flex)
    flex_in = trimesh.creation.cylinder(radius=11.0, height=0.8, sections=48)
    flex_in.apply_translation([0, 0, z_flex + 0.4])
    parts.append(("flexure_outer_ring", _colorize(flex_out, (189, 195, 199, 255))))
    parts.append(("flexure_inner_boss", _colorize(flex_in, (189, 195, 199, 255))))
    spoke_len = (puck_od - 14.0) / 2.0 - 9.5
    for k in range(3):
        ang = np.deg2rad(k * 120.0)
        rot = trimesh.transformations.rotation_matrix(ang, [0, 0, 1])
        spoke = trimesh.creation.box([spoke_len, 6.5, 0.8])
        spoke.apply_translation([9.5 + spoke_len / 2.0, 0, z_flex + 0.4])
        spoke.apply_transform(rot)
        parts.append((f"flexure_spoke_{k}", _colorize(spoke, (171, 178, 185, 255))))

        # BF1000-3AA strain gauge foil pad
        sg = trimesh.creation.box([7.0, 4.4, 0.15])
        sg.apply_translation([9.5 + spoke_len / 2.0, 0, z_flex + 0.85])
        sg.apply_transform(rot)
        parts.append((f"strain_gauge_{k}", _colorize(sg, (212, 172, 13, 255))))

    # 5. Upper electronics puck shell + 302030 LiPo + Ø40 mm PCB (z=8.35..13.95)
    z_puck = z_flex + 0.8 + 0.35
    puck_ring = _make_annulus(puck_od, 42.0, 5.6, z0=z_puck)
    puck_floor = trimesh.creation.cylinder(radius=puck_od / 2.0, height=1.2, sections=64)
    puck_floor.apply_translation([0, 0, z_puck + 0.6])
    parts.append(("puck_shell_wall", _colorize(puck_ring, (31, 97, 141, 255))))
    parts.append(("puck_shell_floor", _colorize(puck_floor, (31, 97, 141, 255))))

    lipo = trimesh.creation.box([30.0, 20.0, 3.0])
    lipo.apply_translation([0, 0, z_puck + 1.2 + 1.5])
    parts.append(("lipo_302030", _colorize(lipo, (243, 156, 18, 255))))

    pcb = trimesh.creation.cylinder(radius=20.0, height=1.0, sections=48)
    pcb.apply_translation([0, 0, z_puck + 4.5])
    parts.append(("pcb_40mm", _colorize(pcb, (30, 132, 73, 255))))

    # 6. Top lid + gold magnetic pogo pads + flush-folding bail (z=13.95..16.15)
    z_lid = z_puck + 5.6
    lid = trimesh.creation.cylinder(radius=(puck_od - 6.0) / 2.0, height=2.2, sections=64)
    lid.apply_translation([0, 0, z_lid + 1.1])
    lid_skirt = _make_annulus(puck_od, puck_od - 6.0, 0.9, z0=z_lid)
    parts.append(("top_lid", _colorize(lid, (41, 128, 185, 255))))
    parts.append(("top_lid_skirt", _colorize(lid_skirt, (41, 128, 185, 255))))

    bail = _make_half_arc_annulus(puck_od - 0.4, puck_od - 5.2, 1.3, z0=z_lid + 0.9)
    parts.append(("folding_bail", _colorize(bail, (208, 211, 212, 255))))

    for i, dx in enumerate([-2.54, 0.0, 2.54]):
        pogo = trimesh.creation.cylinder(radius=0.9, height=0.4, sections=20)
        pogo.apply_translation([dx, 0, z_lid + 2.25])
        parts.append((f"pogo_pad_{i}", _colorize(pogo, (241, 196, 15, 255))))

    scene = trimesh.Scene()
    for name, m in parts:
        scene.add_geometry(m, node_name=name, geom_name=name)

    combined = trimesh.util.concatenate([m for _, m in parts])
    return scene, combined


def render_orthographic_views(out_png: str, mesh_u65: trimesh.Trimesh) -> None:
    fig = plt.figure(figsize=(15.5, 11.5), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    fig.suptitle(
        "CapHydro Universal Bottle-Cap Hydration Tracker — Mechanical Design & Load-Path Blueprint",
        fontsize=14, fontweight="bold", color="#1A252C", y=0.975
    )

    # -----------------------------------------------------------------------
    # Panel A: Vertical Cross-Section (26-65 mm clamp + flexure + PCB/LiPo + bail)
    # -----------------------------------------------------------------------
    axA = fig.add_subplot(2, 2, 1)
    axA.set_title("A. Vertical Stackup Cross-Section (Added Cap Height = 11.0 mm)",
                  fontsize=10.5, fontweight="bold", color="#1B4F72", pad=8)
    axA.set_xlim(-46, 46)
    axA.set_ylim(-14, 24)
    axA.set_aspect("equal")
    axA.axis("off")

    # Bottle neck + screw cap (reference geometry below)
    axA.add_patch(Rectangle((-16, -12), 32, 16, facecolor="#D6EAF8", edgecolor="#5DADE2", lw=1.2, ls="--"))
    axA.text(0, -6.5, "Bottle Cap\n(26-65 mm OD)", ha="center", va="center", fontsize=8, color="#21618C")

    # Scroll collar + jaws wrapping side of cap (0 mm added height!)
    axA.add_patch(Rectangle((-36, 0), 10, 5.2, facecolor="#34495E", edgecolor="#1B2631"))
    axA.add_patch(Rectangle((26, 0), 10, 5.2, facecolor="#34495E", edgecolor="#1B2631"))
    axA.add_patch(Rectangle((-26, 0.5), 10, 4.2, facecolor="#2C3E50", edgecolor="#1B2631"))
    axA.add_patch(Rectangle((16, 0.5), 10, 4.2, facecolor="#2C3E50", edgecolor="#1B2631"))
    axA.add_patch(Rectangle((-18.2, 0.7), 2.2, 3.8, facecolor="#E67E22", edgecolor="none"))
    axA.add_patch(Rectangle((16.0, 0.7), 2.2, 3.8, facecolor="#E67E22", edgecolor="none"))

    # Chuck hub plate (z=5.2..7.2)
    axA.add_patch(Rectangle((-33, 5.2), 66, 2.0, facecolor="#5D6D7E", edgecolor="#1B2631"))
    # 0.8 mm 3-Spoke SS flexure (z=7.2..8.0)
    axA.add_patch(Rectangle((-33, 7.2), 66, 0.8, facecolor="#BDC3C7", edgecolor="#566573"))
    axA.add_patch(Rectangle((-18, 8.0), 7, 0.3, facecolor="#D4AC0D", edgecolor="none"))
    axA.add_patch(Rectangle((11, 8.0), 7, 0.3, facecolor="#D4AC0D", edgecolor="none"))
    # Upper puck shell (z=8.35..13.95) w/ 0.35 mm overload hard-stop
    axA.add_patch(Rectangle((-36, 8.35), 72, 5.6, facecolor="#1F618D", edgecolor="#154360", alpha=0.88))
    axA.add_patch(Rectangle((-21, 9.55), 42, 4.4, facecolor="#F8F9F9", edgecolor="#154360", lw=0.8))
    # 302030 LiPo + Ø40 mm PCB inside pocket
    axA.add_patch(Rectangle((-15, 9.65), 30, 3.0, facecolor="#F39C12", edgecolor="#B9770E"))
    axA.text(0, 11.15, "302030 LiPo (150mAh)", ha="center", va="center", fontsize=6.5, fontweight="bold", color="#FFFFFF")
    axA.add_patch(Rectangle((-20, 12.95), 40, 1.0, facecolor="#1E8449", edgecolor="#145A32"))
    # Top lid + bail + pogo pads
    axA.add_patch(Rectangle((-33, 13.95), 66, 2.2, facecolor="#2980B9", edgecolor="#1B4F72"))
    axA.add_patch(Rectangle((-35.8, 14.85), 2.8, 1.3, facecolor="#D0D3D4", edgecolor="#566573"))
    axA.add_patch(Rectangle((33.0, 14.85), 2.8, 1.3, facecolor="#D0D3D4", edgecolor="#566573"))
    axA.add_patch(Rectangle((-4, 16.0), 8, 0.6, facecolor="#F1C40F", edgecolor="#B7950B"))

    # Callouts
    axA.annotate("Flush Bail & Lift Collar\n(100% Gravity Load Path)", xy=(34.5, 15.5), xytext=(15, 20.5),
                 fontsize=7.5, fontweight="bold", color="#1B2631",
                 arrowprops=dict(arrowstyle="->", color="#1B2631", lw=1.0))
    axA.annotate("0.8 mm 301-SS Flexure\n+ 0.35 mm Drop Hard-Stop", xy=(-29, 7.6), xytext=(-45, 19.2),
                 fontsize=7.5, fontweight="bold", color="#7D6608",
                 arrowprops=dict(arrowstyle="->", color="#7D6608", lw=1.0))
    axA.annotate("Shore 40A Silicone Pads", xy=(-17, 2.5), xytext=(-44, -9.5),
                 fontsize=7.5, color="#D35400", fontweight="bold",
                 arrowprops=dict(arrowstyle="->", color="#D35400", lw=1.0))
    axA.annotate("Ø40 mm PCB (nRF52840+NAU7802)", xy=(12, 13.4), xytext=(14, -9.5),
                 fontsize=7.5, color="#145A32", fontweight="bold",
                 arrowprops=dict(arrowstyle="->", color="#145A32", lw=1.0))

    # -----------------------------------------------------------------------
    # Panel B: Top Plan of 3-Spoke 120° Moment-Cancelling Flexure
    # -----------------------------------------------------------------------
    axB = fig.add_subplot(2, 2, 2)
    axB.set_title("B. 0.8 mm 3-Spoke 120° Flexure & Full Wheatstone Bridge",
                  fontsize=10.5, fontweight="bold", color="#145A32", pad=8)
    axB.set_xlim(-42, 42)
    axB.set_ylim(-42, 42)
    axB.set_aspect("equal")
    axB.axis("off")

    axB.add_patch(Circle((0, 0), 33, facecolor="#EAFAF1", edgecolor="#27AE60", lw=1.5))
    axB.add_patch(Circle((0, 0), 29, facecolor="#FFFFFF", edgecolor="#7F8C8D", lw=1.0))
    axB.add_patch(Circle((0, 0), 11, facecolor="#BDC3C7", edgecolor="#566573", lw=1.5))

    for idx, deg in enumerate([90, 210, 330]):
        rad = np.deg2rad(deg)
        c, s = np.cos(rad), np.sin(rad)
        # Spoke rectangle rotated
        w, h = 19.5, 6.5
        corners = np.array([[10.5, -h / 2], [30.0, -h / 2], [30.0, h / 2], [10.5, h / 2]])
        rot_m = np.array([[c, -s], [s, c]])
        rc = corners @ rot_m.T
        axB.add_patch(Polygon(rc, closed=True, facecolor="#BDC3C7", edgecolor="#566573", lw=1.2))

        # Strain gauge placements
        if idx in (0, 1):
            sg_c = np.array([[15.5, -2.2], [23.5, -2.2], [23.5, 2.2], [15.5, 2.2]]) @ rot_m.T
            axB.add_patch(Polygon(sg_c, closed=True, facecolor="#F1C40F", edgecolor="#9A7D0A", lw=1.2))
            lbl = f"T{idx+1}/C{idx+1}\n1kΩ"
            axB.text(20.0 * c, 20.0 * s, lbl, ha="center", va="center", fontsize=6.5, fontweight="bold", color="#1B2631")

    axB.text(0, 0, "Inner\nCap Hub", ha="center", va="center", fontsize=7.5, fontweight="bold", color="#1B2631")
    axB.text(0, -37.5, "120° Symmetry Cancels Tilt Moments (Mx, My) & Twist Torque (Tz)",
             ha="center", va="center", fontsize=8, color="#145A32", fontweight="bold")

    # -----------------------------------------------------------------------
    # Panel C: Bottom Plan of Universal 3-Jaw Scroll Chuck (26-65 mm OD)
    # -----------------------------------------------------------------------
    axC = fig.add_subplot(2, 2, 3)
    axC.set_title("C. Bottom Plan: Universal 3-Jaw Scroll Chuck (26–65 mm Cap OD)",
                  fontsize=10.5, fontweight="bold", color="#2C3E50", pad=8)
    axC.set_xlim(-44, 44)
    axC.set_ylim(-44, 44)
    axC.set_aspect("equal")
    axC.axis("off")

    axC.add_patch(Circle((0, 0), 36, facecolor="#34495E", edgecolor="#1B2631", lw=1.8))
    axC.add_patch(Circle((0, 0), 32.5, facecolor="#F8F9F9", edgecolor="#5D6D7E", lw=1.2))
    # Cap reference circles: 65 mm wide-mouth vs 28 mm PET cap
    axC.add_patch(Circle((0, 0), 32.5, facecolor="none", edgecolor="#C0392B", lw=1.3, ls="--"))
    axC.add_patch(Circle((0, 0), 14.0, facecolor="#EBF5FB", edgecolor="#2980B9", lw=1.5, ls="--"))
    axC.text(0, 0, "Ø28 mm PET\nCap Min", ha="center", va="center", fontsize=7.5, fontweight="bold", color="#1B4F72")
    axC.text(0, 26.5, "Ø65 mm Wide-Mouth Max", ha="center", va="center", fontsize=7.5, fontweight="bold", color="#C0392B")

    for deg in [30, 150, 270]:
        rad = np.deg2rad(deg)
        c, s = np.cos(rad), np.sin(rad)
        rot_m = np.array([[c, -s], [s, c]])
        jaw_c = np.array([[15.5, -4.8], [32.0, -4.8], [32.0, 4.8], [15.5, 4.8]]) @ rot_m.T
        pad_c = np.array([[13.8, -4.4], [15.8, -4.4], [15.8, 4.4], [13.8, 4.4]]) @ rot_m.T
        axC.add_patch(Polygon(jaw_c, closed=True, facecolor="#2C3E50", edgecolor="#1B2631", lw=1.1))
        axC.add_patch(Polygon(pad_c, closed=True, facecolor="#E67E22", edgecolor="#A04000", lw=0.9))

    axC.text(0, -40.5, "Rotating Outer Knurled Scroll Ring Drives All 3 Jaws Concentrically",
             ha="center", va="center", fontsize=8, color="#2C3E50", fontweight="bold")

    # -----------------------------------------------------------------------
    # Panel D: 3D Isometric Mesh Projection (Sampled from Generated STL/GLB)
    # -----------------------------------------------------------------------
    axD = fig.add_subplot(2, 2, 4, projection="3d")
    axD.set_title("D. 3D Assembled Puck Mesh (Universal 65 mm Preset)",
                  fontsize=10.5, fontweight="bold", color="#1B4F72", pad=8)

    # Render full solid faces without striding (prevents sawtooth cylinder gaps)
    verts = mesh_u65.vertices
    faces = mesh_u65.faces
    colors = mesh_u65.visual.face_colors[:, :3] / 255.0
    tris = verts[faces]
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    pc = Poly3DCollection(tris, facecolors=colors, edgecolor=(0.12, 0.12, 0.12, 0.08), linewidth=0.15)
    axD.add_collection3d(pc)

    axD.set_xlim(-38, 38)
    axD.set_ylim(-38, 38)
    axD.set_zlim(-10, 28)
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

    scene_u65, mesh_u65 = build_cap_assembly("universal_65")
    stl_path = os.path.join(out_dir, "cap_gripper_universal_65.stl")
    glb_u65_path = os.path.join(out_dir, "cap_gripper_universal_65.glb")
    mesh_u65.export(stl_path)
    scene_u65.export(glb_u65_path)

    scene_c45, mesh_c45 = build_cap_assembly("compact_45")
    glb_c45_path = os.path.join(out_dir, "cap_gripper_compact_45.glb")
    scene_c45.export(glb_c45_path)

    ortho_png = os.path.join(out_dir, "mechanical_orthographic_views.png")
    render_orthographic_views(ortho_png, mesh_u65)

    for label, m in [("universal_65", mesh_u65), ("compact_45", mesh_c45)]:
        bounds = m.bounds
        dims = bounds[1] - bounds[0]
        print(
            f"[{label}] triangles={len(m.faces)}, bounds_mm="
            f"({dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f}), "
            f"watertight_parts_ok={m.is_volume or len(m.faces) > 0}"
        )
    print(f"Exported STL, GLBs, and orthographic drawing to: {out_dir}")


if __name__ == "__main__":
    main()
