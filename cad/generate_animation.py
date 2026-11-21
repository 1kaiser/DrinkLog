#!/usr/bin/env python3
"""
Generate an animated multi-stage demonstration GIF (< 1.8 MiB) & MP4 showing:
  1. Universal 3-jaw scroll chuck closing onto a bottle cap (65 -> 32 mm OD)
  2. DrinkLog drop-on clamping & flush finger bail flip-up
  3. Bottle lift weighing via 0.8 mm 3-spoke flexure (1180 g -> LED lock)
  4. Unscrew Auto-Tare (0 g) -> Sip (-210 mL) -> Re-cap lift (970 g) -> BLE Health Connect ACK
  5. Side IP67 TPU USB-C plug opening + USB-C 5V Charge & Native CDC/DFU Debug
"""

from __future__ import annotations

import math
import os
import subprocess
from typing import List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, FancyBboxPatch, Polygon, Rectangle
import numpy as np
from PIL import Image


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def draw_frame(frame_idx: int, total_frames: int) -> Image.Image:
    # 5 stages across 120 frames (10 fps = 12.0 s loop)
    fig = plt.figure(figsize=(8.2, 4.5), dpi=100)
    fig.patch.set_facecolor("#FFFFFF")

    ax_mech = fig.add_axes([0.02, 0.08, 0.56, 0.80])
    ax_hud = fig.add_axes([0.60, 0.08, 0.38, 0.80])

    ax_mech.set_xlim(-55, 55)
    ax_mech.set_ylim(-68, 42)
    ax_mech.set_aspect("equal")
    ax_mech.axis("off")

    ax_hud.set_xlim(0, 100)
    ax_hud.set_ylim(0, 100)
    ax_hud.axis("off")

    # Stage timing (0..119)
    # 0..23:   Stage 1 - Universal Scroll Clamp & Drop-on Attachment
    # 24..47:  Stage 2 - Bail Flip-Up & Cap-Lift Baseline Weigh (1180 g)
    # 48..71:  Stage 3 - Unscrew Auto-Tare (0 g) & Drink 210 mL
    # 72..95:  Stage 4 - Re-Cap Lift (970 g) & BLE Health Connect Sync (+210 mL)
    # 96..119: Stage 5 - IP67 TPU Plug Open -> USB-C 5V Charge & Debug CLI
    if frame_idx < 24:
        stage = 1
        u = _ease(frame_idx / 23.0)
        cap_drop_y = 22.0 * (1.0 - u)
        jaw_r = 28.0 - 12.0 * u
        lift_y = 0.0
        bail_deg = 0.0
        flex_dy = 0.0
        water_frac = 0.85
        mass_g = 0
        cum_ml = 0
        power_mode = "SLEEP  6.4 uA"
        power_col = "#16A085"
        stage_title = "1. UNIVERSAL GRIPPER CLAMP"
        stage_desc = "3-jaw scroll chuck adjusts\n26-65 mm OD & locks onto cap"
        plug_open = 0.0
        cable_in = 0.0
        ble_pulse = 0.0
        led_col = "#7F8C8D"
    elif frame_idx < 48:
        stage = 2
        u = _ease((frame_idx - 24) / 23.0)
        cap_drop_y = 0.0
        jaw_r = 16.0
        bail_deg = 90.0 * min(1.0, u * 1.8)
        lift_y = 9.0 * math.sin(min(1.0, max(0.0, (u - 0.25) / 0.75)) * math.pi)
        flex_dy = -1.1 * (lift_y / 9.0)
        water_frac = 0.85
        mass_g = int(round(1180 * min(1.0, lift_y / 6.0))) if lift_y > 1.0 else 1180
        cum_ml = 0
        power_mode = "WEIGH  4.0 mA" if lift_y > 1.0 else "IDLE   6.4 uA"
        power_col = "#D4AC0D" if lift_y > 1.0 else "#16A085"
        stage_title = "2. CAP-LIFT BASELINE WEIGH"
        stage_desc = "Bail routes 100% weight via\n0.8 mm flexure (m = Fz / az)"
        plug_open = 0.0
        cable_in = 0.0
        ble_pulse = max(0.0, (u - 0.65) / 0.35)
        led_col = "#27AE60" if u > 0.55 else "#F1C40F"
    elif frame_idx < 72:
        stage = 3
        u = _ease((frame_idx - 48) / 23.0)
        cap_drop_y = 14.0 * math.sin(u * math.pi)
        jaw_r = 16.0
        bail_deg = 0.0
        lift_y = 0.0
        flex_dy = 0.0
        water_frac = 0.85 - 0.22 * min(1.0, max(0.0, (u - 0.25) / 0.5))
        mass_g = 0
        cum_ml = 0
        power_mode = "AUTO-TARE 0 g"
        power_col = "#2980B9"
        stage_title = "3. UNSCREW AUTO-TARE & SIP"
        stage_desc = "Unweighted cap EMA resets zero\ndrift while user drinks 210 mL"
        plug_open = 0.0
        cable_in = 0.0
        ble_pulse = 0.0
        led_col = "#3498DB"
    elif frame_idx < 96:
        stage = 4
        u = _ease((frame_idx - 72) / 23.0)
        cap_drop_y = 0.0
        jaw_r = 16.0
        bail_deg = 90.0
        lift_y = 8.5 * math.sin(min(1.0, u * 1.2) * math.pi)
        flex_dy = -0.9 * (lift_y / 8.5)
        water_frac = 0.63
        mass_g = 970
        cum_ml = 210 if u > 0.35 else 0
        power_mode = "BLE SYNC  8 mA"
        power_col = "#8E44AD"
        stage_title = "4. DELTA SYNC TO GOOGLE HEALTH"
        stage_desc = "1180 g -> 970 g = +210 mL\nHealth Connect ACK verified"
        plug_open = 0.0
        cable_in = 0.0
        ble_pulse = (u * 2.2) % 1.0
        led_col = "#27AE60"
    else:
        stage = 5
        u = _ease((frame_idx - 96) / 23.0)
        cap_drop_y = 0.0
        jaw_r = 16.0
        bail_deg = 0.0
        lift_y = 0.0
        flex_dy = 0.0
        water_frac = 0.63
        mass_g = 970
        cum_ml = 210
        plug_open = min(1.0, u * 2.0)
        cable_in = max(0.0, (u - 0.35) / 0.65)
        ble_pulse = 0.0
        power_mode = "USB-C 5V + DEBUG"
        power_col = "#C0392B"
        stage_title = "5. IP67 USB-C CHARGE & DEBUG"
        stage_desc = "Amphenol IPX8 + TPU plug\n5V BQ25180 + Native CDC/DFU"
        led_col = "#E74C3C" if cable_in > 0.6 else "#7F8C8D"

    # Global vertical banner
    fig.text(
        0.5, 0.945,
        "DrinkLog — Universal Bottle-Cap Attachment, Hydration Tracking & IP67 USB-C Debug",
        ha="center", va="center", fontsize=11.5, fontweight="bold", color="#1A252C"
    )

    # --- Table surface reference ---
    ax_mech.plot([-52, 52], [-60, -60], color="#95A5A6", lw=1.5, ls="--")
    ax_mech.text(-49, -63.5, "Table Surface", fontsize=7.5, color="#7F8C8D")

    # --- Bottle body & dynamic water fill ---
    by0 = -60.0 + lift_y
    bottle_body = FancyBboxPatch(
        (-24, by0), 48, 44,
        boxstyle="round,pad=0,rounding_size=5",
        facecolor="#EBF5FB", edgecolor="#2980B9", lw=1.8, zorder=2
    )
    ax_mech.add_patch(bottle_body)
    fill_h = 38.0 * water_frac
    ax_mech.add_patch(Rectangle((-22.5, by0 + 1.5), 45, fill_h, facecolor="#5DADE2", alpha=0.65, zorder=2))
    ax_mech.text(0, by0 + 12, f"{int(round(water_frac * 880))} mL", ha="center", va="center",
                 fontsize=8.5, fontweight="bold", color="#154360", zorder=3)
    # Bottle neck & screw cap
    ax_mech.add_patch(Rectangle((-13, by0 + 44), 26, 6, facecolor="#D6EAF8", edgecolor="#2980B9", lw=1.5, zorder=3))
    ax_mech.add_patch(Rectangle((-15, by0 + 50), 30, 8, facecolor="#5D6D7E", edgecolor="#1B2631", lw=1.4, zorder=3))

    # --- DrinkLog Assembly (shifted by lift_y + cap_drop_y) ---
    cy0 = by0 + 51.0 + cap_drop_y
    # Scroll collar & sliding jaws
    ax_mech.add_patch(Rectangle((-35, cy0), 70, 5.2, facecolor="#34495E", edgecolor="#1B2631", lw=1.1, zorder=4))
    ax_mech.add_patch(Rectangle((-jaw_r - 12, cy0 + 0.6), 12, 4.0, facecolor="#2C3E50", edgecolor="#1B2631", zorder=5))
    ax_mech.add_patch(Rectangle((jaw_r, cy0 + 0.6), 12, 4.0, facecolor="#2C3E50", edgecolor="#1B2631", zorder=5))
    ax_mech.add_patch(Rectangle((-jaw_r - 2.0, cy0 + 0.8), 2.2, 3.6, facecolor="#E67E22", edgecolor="none", zorder=6))
    ax_mech.add_patch(Rectangle((jaw_r - 0.2, cy0 + 0.8), 2.2, 3.6, facecolor="#E67E22", edgecolor="none", zorder=6))

    # Hub + 0.8 mm 3-spoke SS flexure (shows micro-strain flex during lift!)
    ax_mech.add_patch(Rectangle((-32, cy0 + 5.2), 64, 2.0, facecolor="#5D6D7E", edgecolor="#1B2631", zorder=5))
    ax_mech.plot([-31, -11, 11, 31],
                 [cy0 + 7.6 + flex_dy, cy0 + 7.6, cy0 + 7.6, cy0 + 7.6 + flex_dy],
                 color="#BDC3C7", lw=3.0, zorder=6)

    # Upper PCB / LiPo puck + IP67 O-ring + USB-C port
    py0 = cy0 + 8.3 + flex_dy
    ax_mech.add_patch(Rectangle((-35, py0), 70, 5.6, facecolor="#1F618D", edgecolor="#154360", lw=1.2, zorder=6))
    ax_mech.add_patch(Rectangle((-15, py0 + 1.0), 30, 3.0, facecolor="#F39C12", edgecolor="#B9770E", lw=0.8, zorder=7))
    ax_mech.add_patch(Rectangle((-21, py0 + 4.2), 42, 0.9, facecolor="#0B5345", edgecolor="#145A32", lw=0.6, zorder=7))
    ax_mech.add_patch(Rectangle((-33, py0 + 5.6), 66, 2.2, facecolor="#2980B9", edgecolor="#1B4F72", lw=1.0, zorder=7))
    # Status LED
    ax_mech.add_patch(Circle((22, py0 + 7.2), 1.4, facecolor=led_col, edgecolor="#1B2631", lw=0.6, zorder=9))

    # Pivoting finger bail
    bail_h = 2.0 + 12.0 * math.sin(math.radians(bail_deg))
    ax_mech.plot([-34, -34, 34, 34],
                 [py0 + 6.5, py0 + 6.5 + bail_h, py0 + 6.5 + bail_h, py0 + 6.5],
                 color="#AEB6BF", lw=3.2, solid_capstyle="round", zorder=8)

    # Left IP67 USB-C port, TPU plug, and engaging cable
    ax_mech.add_patch(Rectangle((-36.5, py0 + 1.4), 4.0, 2.8, facecolor="#2C3E50", edgecolor="#1B2631", zorder=8))
    plug_x = -38.8 - 10.0 * plug_open
    plug_y = py0 + 1.4 - 6.0 * plug_open
    ax_mech.add_patch(Rectangle((plug_x, plug_y), 2.6, 2.8, facecolor="#E74C3C", edgecolor="#922B21", zorder=9))
    if cable_in > 0.05:
        cx_end = -36.5 - 18.0 * (1.0 - cable_in)
        ax_mech.add_patch(Rectangle((cx_end - 11.0, py0 + 1.1), 11.0, 3.4, facecolor="#34495E", edgecolor="#1B2631", zorder=10))
        ax_mech.plot([cx_end - 18.0, cx_end - 11.0], [py0 + 2.8, py0 + 2.8], color="#1C2833", lw=3.5, zorder=9)
        ax_mech.text(-52, py0 + 9.5, "5V + USB CDC", fontsize=7.2, fontweight="bold", color="#C0392B")

    # BLE Wave Rings + Phone Icon in Stage 4
    if stage == 4:
        for r_ring in [12 + 18 * ble_pulse, 20 + 18 * ((ble_pulse + 0.4) % 1.0)]:
            ax_mech.add_patch(Arc((30, py0 + 6), r_ring, r_ring, angle=0, theta1=-25, theta2=55,
                                  color="#8E44AD", lw=1.8, alpha=0.85, zorder=9))
        # Android Health Connect miniature phone
        ax_mech.add_patch(FancyBboxPatch((38, 12), 14, 24, boxstyle="round,pad=0,rounding_size=2",
                                         facecolor="#F4ECF7", edgecolor="#8E44AD", lw=1.5, zorder=9))
        ax_mech.text(45, 24, "Health\nConnect\n+210mL", ha="center", va="center",
                     fontsize=6.5, fontweight="bold", color="#4A235A", zorder=10)

    # Bottom Clamp Diameter Inset Badge
    ax_mech.add_patch(FancyBboxPatch((-53, -55), 25, 28, boxstyle="round,pad=0,rounding_size=2",
                                     facecolor="#F8F9F9", edgecolor="#BDC3C7", lw=1.0, zorder=3))
    ax_mech.add_patch(Circle((-40.5, -39.5), 9.0, facecolor="#34495E", edgecolor="#1B2631", lw=1.0, zorder=4))
    ax_mech.add_patch(Circle((-40.5, -39.5), jaw_r * 0.25, facecolor="#EBF5FB", edgecolor="#2980B9", lw=1.0, zorder=5))
    for k in range(3):
        a = math.radians(k * 120 + 30)
        jr = jaw_r * 0.25
        ax_mech.plot([-40.5 + jr * math.cos(a), -40.5 + 8.3 * math.cos(a)],
                     [-39.5 + jr * math.sin(a), -39.5 + 8.3 * math.sin(a)],
                     color="#E67E22", lw=2.3, zorder=6)
    ax_mech.text(-40.5, -52.0, f"Cap Ø{int(round(jaw_r * 2))}mm", ha="center", va="center",
                 fontsize=6.5, fontweight="bold", color="#1B2631", zorder=7)

    # --- Right HUD Telemetry Panel ---
    ax_hud.add_patch(FancyBboxPatch((2, 2), 96, 96, boxstyle="round,pad=0,rounding_size=4",
                                    facecolor="#F8F9F9", edgecolor="#D5D8DC", lw=1.5))

    # Stage Banner
    ax_hud.add_patch(FancyBboxPatch((6, 78), 88, 16, boxstyle="round,pad=0,rounding_size=3",
                                    facecolor="#1B4F72", edgecolor="none"))
    ax_hud.text(50, 88.5, stage_title, ha="center", va="center", fontsize=8.5, fontweight="bold", color="#FFFFFF")
    ax_hud.text(50, 81.8, f"Stage {stage}/5", ha="center", va="center", fontsize=7.5, color="#AED6F1")

    ax_hud.text(50, 68.5, stage_desc, ha="center", va="center", fontsize=8.3, color="#2C3E50", fontweight="bold")

    # Mass & Health Connect Cards
    ax_hud.add_patch(FancyBboxPatch((6, 40), 42, 20, boxstyle="round,pad=0,rounding_size=2",
                                    facecolor="#EBF5FB", edgecolor="#2980B9", lw=1.2))
    ax_hud.text(27, 54, "Measured Mass", ha="center", va="center", fontsize=7.2, color="#1B4F72", fontweight="bold")
    ax_hud.text(27, 45.5, f"{mass_g} g", ha="center", va="center", fontsize=12.5, color="#154360", fontweight="bold")

    ax_hud.add_patch(FancyBboxPatch((52, 40), 42, 20, boxstyle="round,pad=0,rounding_size=2",
                                    facecolor="#EAFAF1", edgecolor="#27AE60", lw=1.2))
    ax_hud.text(73, 54, "Google Health", ha="center", va="center", fontsize=7.2, color="#145A32", fontweight="bold")
    ax_hud.text(73, 45.5, f"+{cum_ml} mL", ha="center", va="center", fontsize=12.5, color="#1E8449", fontweight="bold")

    # Power State Pill
    ax_hud.add_patch(FancyBboxPatch((6, 22), 88, 13, boxstyle="round,pad=0,rounding_size=2",
                                    facecolor=power_col, edgecolor="none"))
    ax_hud.text(50, 28.5, f"POWER: {power_mode}", ha="center", va="center", fontsize=8.5, fontweight="bold", color="#FFFFFF")

    # Hardware Footer
    ax_hud.text(50, 11.5, "nRF52840 (MDBT50Q) + NAU7802\nBMA400 + Amphenol IPX8 USB-C\n~12 mo / charge (302030 LiPo)",
                ha="center", va="center", fontsize=7.0, color="#566573")

    fig.canvas.draw()
    rgba = np.asarray(fig.canvas.buffer_rgba())
    img = Image.fromarray(rgba, mode="RGBA").convert("RGB")
    plt.close(fig)
    return img


def main() -> None:
    cad_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(cad_dir, ".."))
    out_dir = os.path.join(repo_root, "outputs")
    os.makedirs(out_dir, exist_ok=True)

    total_frames = 120
    frames_rgb: List[Image.Image] = []
    frames_pal: List[Image.Image] = []

    for i in range(total_frames):
        im = draw_frame(i, total_frames)
        frames_rgb.append(im)
        frames_pal.append(im.quantize(colors=96, method=Image.Quantize.MEDIANCUT))

    gif_path = os.path.join(out_dir, "drinklog_attachment_animation.gif")
    frames_pal[0].save(
        gif_path,
        save_all=True,
        append_images=frames_pal[1:],
        duration=100,  # 10 fps -> 12.0 s loop
        loop=0,
        optimize=True,
    )
    gif_size = os.path.getsize(gif_path)

    # Save 4 storyboard frames to /tmp for visual inspection
    for idx, tag in [(12, "stage1"), (38, "stage2"), (84, "stage4"), (112, "stage5")]:
        frames_rgb[idx].save(f"/tmp/drinklog_anim_{tag}.png")

    # Encode MP4 via ffmpeg using pipe
    mp4_path = os.path.join(out_dir, "drinklog_attachment_animation.mp4")
    w, h = frames_rgb[0].size
    cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{w}x{h}", "-pix_fmt", "rgb24", "-r", "10", "-i", "-",
        "-an", "-vcodec", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
        mp4_path,
    ]
    proc = subprocess.run(cmd, input=b"".join(im.tobytes() for im in frames_rgb),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    _ = proc

    print(f"[Animation] GIF: {gif_path} ({gif_size / 1024:.1f} KiB, {total_frames} frames)")
    print(f"[Animation] MP4: {mp4_path} ({os.path.getsize(mp4_path) / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
