#!/usr/bin/env python3
"""
Generate transparent RGBA HUD overlay stamps (hud_stage_1.png .. hud_stage_5.png)
and the 3D Android smartphone Health Connect texture (phone_screen_hc.png)
for the pure Node.js + Clang WASM + Dawn WebGPU renderer.
"""

from __future__ import annotations

import os
import zlib
from PIL import Image, ImageDraw, ImageFont

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


STAGES = [
    (
        1,
        "1.1x Cap Gripper (33.6 mm Shell)",
        "Compliant collet locks onto 30.5 mm PET\ncap around universal Ø28 mm PCB core.",
        "0 g",
        "+0 mL",
        "POWER: SLEEP 6.4 uA",
        (22, 160, 133, 255),
    ),
    (
        2,
        "Bail-Lift Baseline Weighing",
        "Slim folding bail routes 100% weight via\nØ30 mm 3-spoke flexure (m = Fz / az).",
        "1180 g",
        "+0 mL",
        "POWER: WEIGH 4.0 mA",
        (212, 172, 13, 255),
    ),
    (
        3,
        "Cap-Off Auto-Tare & Sip (-210 mL)",
        "Unscrewed cap updates zero-offset EMA\n(0.8 old + 0.2 raw), eliminating drift.",
        "0 g",
        "+0 mL",
        "POWER: AUTO-TARE 0 g",
        (41, 128, 185, 255),
    ),
    (
        4,
        "BLE Sync to Google Health Connect",
        "1180 g -> 970 g (+210 mL) pushed on\nGATT 0002; ring clears after HC ACK.",
        "970 g",
        "+210 mL",
        "POWER: BLE SYNC 8 mA",
        (142, 68, 173, 255),
    ),
    (
        5,
        "IP67 USB-C Charge & Native Debug",
        "Captive TPU plug opens to reveal IPX8\nUSB-C (BQ25180 5V + nRF52840 CDC).",
        "970 g",
        "+210 mL",
        "POWER: USB-C 5V + DEBUG",
        (192, 57, 43, 255),
    ),
]


def build_stage_huds(out_dir: str, width: int = 960, height: int = 540) -> None:
    os.makedirs(out_dir, exist_ok=True)
    f_title = _font(FONT_BOLD, 15)
    f_badge = _font(FONT_BOLD, 11)
    f_head = _font(FONT_BOLD, 14)
    f_body = _font(FONT_REG, 12)
    f_lbl = _font(FONT_BOLD, 10)
    f_val = _font(FONT_BOLD, 17)
    f_foot = _font(FONT_REG, 10)

    for num, head, body, mass_s, hc_s, pwr_s, pwr_col in STAGES:
        im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)

        # Top-Left Stage Card (keeps pure transparent margin at corners)
        lx0, ly0, lx1, ly1 = 18, 16, 344, 116
        d.rounded_rectangle([lx0, ly0, lx1, ly1], radius=12, fill=(255, 255, 255, 232), outline=(213, 221, 229, 255), width=2)
        d.text((lx0 + 14, ly0 + 12), "HydroCap 3D", font=f_title, fill=(21, 67, 96, 255))
        d.rounded_rectangle([lx0 + 126, ly0 + 11, lx0 + 212, ly0 + 30], radius=9, fill=(27, 79, 114, 255))
        d.text((lx0 + 136, ly0 + 14), f"STAGE {num}/5", font=f_badge, fill=(255, 255, 255, 255))
        d.text((lx0 + 14, ly0 + 37), head, font=f_head, fill=(27, 38, 49, 255))
        d.multiline_text((lx0 + 14, ly0 + 58), body, font=f_body, fill=(74, 85, 104, 255), spacing=3)

        # Top-Right Telemetry Card
        rx0, ry0, rx1, ry1 = width - 252, 16, width - 18, 122
        d.rounded_rectangle([rx0, ry0, rx1, ry1], radius=12, fill=(255, 255, 255, 232), outline=(213, 221, 229, 255), width=2)
        # Two metric boxes
        d.rounded_rectangle([rx0 + 10, ry0 + 10, rx0 + 112, ry0 + 54], radius=7, fill=(235, 245, 251, 255), outline=(133, 193, 233, 255), width=1)
        d.text((rx0 + 61, ry0 + 18), "BOTTLE MASS", font=f_lbl, fill=(44, 62, 80, 255), anchor="mm")
        d.text((rx0 + 61, ry0 + 39), mass_s, font=f_val, fill=(21, 67, 96, 255), anchor="mm")

        d.rounded_rectangle([rx0 + 120, ry0 + 10, rx0 + 224, ry0 + 54], radius=7, fill=(234, 250, 241, 255), outline=(130, 224, 170, 255), width=1)
        d.text((rx0 + 172, ry0 + 18), "HEALTH CONNECT", font=f_lbl, fill=(44, 62, 80, 255), anchor="mm")
        d.text((rx0 + 172, ry0 + 39), hc_s, font=f_val, fill=(30, 132, 73, 255), anchor="mm")

        # Power Pill
        d.rounded_rectangle([rx0 + 10, ry0 + 60, rx1 - 10, ry0 + 84], radius=7, fill=pwr_col)
        d.text(((rx0 + rx1) // 2, ry0 + 72), pwr_s, font=f_badge, fill=(255, 255, 255, 255), anchor="mm")
        d.text(((rx0 + rx1) // 2, ry0 + 95), "Node.js + Clang WASM + Dawn WebGPU", font=f_foot, fill=(86, 101, 115, 255), anchor="mm")

        im.save(os.path.join(out_dir, f"hud_stage_{num}.png"))
        with open(os.path.join(out_dir, f"hud_stage_{num}.rgba.zlib"), "wb") as fz:
            fz.write(zlib.compress(im.tobytes(), level=6))


def build_phone_texture(out_path: str) -> None:
    im = Image.new("RGBA", (256, 512), (248, 249, 250, 255))
    d = ImageDraw.Draw(im)
    f_hdr = _font(FONT_BOLD, 22)
    f_sub = _font(FONT_REG, 13)
    f_big = _font(FONT_BOLD, 44)
    f_ok = _font(FONT_BOLD, 17)
    f_mono = _font(FONT_MONO, 14)

    d.rectangle([0, 0, 256, 86], fill=(27, 79, 114, 255))
    d.text((128, 34), "Health Connect", font=f_hdr, fill=(255, 255, 255, 255), anchor="mm")
    d.text((128, 62), "HydrationRecord Sync", font=f_sub, fill=(174, 214, 241, 255), anchor="mm")

    d.rounded_rectangle([20, 112, 236, 340], radius=18, fill=(255, 255, 255, 255), outline=(39, 174, 96, 255), width=4)
    d.text((128, 192), "+210 mL", font=f_big, fill=(30, 132, 73, 255), anchor="mm")
    d.text((128, 246), "ACK Verified", font=f_ok, fill=(39, 174, 96, 255), anchor="mm")
    d.text((128, 294), "1180 g -> 970 g", font=f_mono, fill=(86, 101, 115, 255), anchor="mm")

    d.rounded_rectangle([20, 366, 236, 468], radius=12, fill=(235, 245, 251, 255), outline=(133, 193, 233, 255), width=2)
    d.text((128, 402), "CapHydro GATT 0002", font=f_ok, fill=(21, 67, 96, 255), anchor="mm")
    d.text((128, 434), "clientRecordId #002", font=f_sub, fill=(41, 128, 185, 255), anchor="mm")
    im.save(out_path)
    with open(out_path.replace(".png", ".rgba.zlib"), "wb") as fz:
        fz.write(zlib.compress(im.tobytes(), level=6))


def main() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    hud_dir = os.path.join(base_dir, "hud_cache")
    build_stage_huds(hud_dir)
    build_phone_texture(os.path.join(hud_dir, "phone_screen_hc.png"))
    print(f"[HUD] Generated 5 transparent stage HUD PNGs + phone texture in {hud_dir}")


if __name__ == "__main__":
    main()
