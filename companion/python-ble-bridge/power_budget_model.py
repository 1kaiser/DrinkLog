#!/usr/bin/env python3
"""
Power-budget & 24-hour gravimetric sip-detection simulator for CapHydro.
Models standby leakage + event wake currents across 5 MCU/sensor topologies
and renders outputs/power_budget_and_sip_simulation.png.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from protocol import simulate_24h_bottle_day


@dataclass(frozen=True)
class HardwareProfile:
    name: str
    short_label: str
    mcu_sleep_ua: float
    imu_sleep_ua: float
    adc_sleep_ua: float
    active_bridge_adc_ma: float
    active_mcu_ble_ma: float
    active_duration_s: float = 1.2
    adc_on_s: float = 0.6


PROFILES: List[HardwareProfile] = [
    HardwareProfile("XIAO nRF52840 + BMA400 (Primary V1)", "nRF52840\n+ BMA400", 5.0, 0.9, 0.5, 4.0, 6.0),
    HardwareProfile("XIAO nRF52840 Sense (LSM6DS3 LP)", "nRF52840\nSense (LP)", 5.0, 38.0, 0.5, 4.0, 6.0),
    HardwareProfile("XIAO ESP32-C6 + BMA400 (Budget)", "ESP32-C6\n+ BMA400", 17.0, 0.9, 0.5, 4.0, 18.0),
    HardwareProfile("XIAO ESP32-C3 + BMA400", "ESP32-C3\n+ BMA400", 44.0, 0.9, 0.5, 4.0, 18.0),
    HardwareProfile("XIAO RP2040 + Ext BLE (No LP RTC)", "RP2040\n(+Ext BLE)", 650.0, 0.9, 0.5, 4.0, 12.0),
]


def compute_battery_metrics(
    profile: HardwareProfile,
    battery_mah: float = 150.0,
    usable_fraction: float = 0.80,
    lifts_per_day: int = 30,
    monthly_self_discharge_pct: float = 2.0,
) -> Dict[str, float]:
    sleep_ua = profile.mcu_sleep_ua + profile.imu_sleep_ua + profile.adc_sleep_ua
    active_s_day = lifts_per_day * profile.active_duration_s
    sleep_h_day = (86400.0 - active_s_day) / 3600.0

    sleep_mah_day = (sleep_ua / 1000.0) * sleep_h_day
    event_mah = (
        profile.active_bridge_adc_ma * profile.adc_on_s
        + profile.active_mcu_ble_ma * profile.active_duration_s
    ) / 3600.0
    active_mah_day = lifts_per_day * event_mah
    total_mah_day = sleep_mah_day + active_mah_day

    usable_mah = battery_mah * usable_fraction
    theoretical_days = usable_mah / total_mah_day

    # Include lithium self-discharge loss iteratively by month
    rem = usable_mah
    realistic_days = 0.0
    while rem > 0.0 and realistic_days < 3650.0:
        step = min(30.0, rem / total_mah_day)
        rem -= step * total_mah_day
        rem -= (battery_mah * (monthly_self_discharge_pct / 100.0)) * (step / 30.0)
        realistic_days += step

    return {
        "sleep_ua": sleep_ua,
        "sleep_mah_day": sleep_mah_day,
        "active_mah_day": active_mah_day,
        "total_mah_day": total_mah_day,
        "theoretical_days": theoretical_days,
        "realistic_days": realistic_days,
        "realistic_months": realistic_days / 30.4375,
    }


def generate_summary_figure(out_png: str) -> None:
    results = [(p, compute_battery_metrics(p)) for p in PROFILES]
    events = simulate_24h_bottle_day()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 5.8), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    fig.suptitle(
        "CapHydro Power-Budget Analysis (150 mAh 302030 LiPo) & 24-Hour Gravimetric Sip Tracking",
        fontsize=13, fontweight="bold", color="#1A252C", y=0.98
    )

    # Panel A: Battery life comparison
    labels = [p.short_label for p, _ in results]
    months = [r["realistic_months"] for _, r in results]
    sleeps = [r["sleep_ua"] for _, r in results]
    colors = ["#1E8449", "#2980B9", "#D4AC0D", "#E67E22", "#C0392B"]

    bars = ax1.bar(labels, months, color=colors, edgecolor="#1B2631", linewidth=0.9, width=0.58)
    ax1.set_ylabel("Estimated Runtime per Charge (Months)", fontsize=10, fontweight="bold")
    ax1.set_title("A. MCU Platform Runtime (30 Lifts/Day, 150 mAh LiPo)", fontsize=10.8, fontweight="bold", color="#1B4F72")
    ax1.set_ylim(0, max(months) * 1.24)
    ax1.grid(axis="y", linestyle="--", alpha=0.45)
    ax1.tick_params(axis="x", labelsize=8.5)

    for bar, m_val, s_ua in zip(bars, months, sleeps):
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height() + 0.35,
            f"{m_val:.1f} mo\n({s_ua:.1f} uA)",
            ha="center", va="bottom", fontsize=8.0, fontweight="bold", color="#1A252C"
        )

    # Panel B: Simulated 24-hour bottle mass & cumulative Health Connect hydration
    hours = [ev.uptime_s / 3600.0 for ev in events]
    masses = [ev.bottle_mass_g for ev in events]
    cum_ml = np.cumsum([max(0, ev.delta_ml) for ev in events])

    ax2.step(hours, masses, where="post", color="#2980B9", linewidth=2.2, label="Bottle Mass (g)")
    ax2.scatter(hours, masses, color="#1F618D", s=38, zorder=5)

    # Annotate refills & sips cleanly
    for h, m, ev in zip(hours, masses, events):
        if ev.seq > 1 and ev.delta_ml == 0:
            ax2.annotate("Refill", xy=(h, m), xytext=(h - 0.6, m + 95),
                         fontsize=8, fontweight="bold", color="#1E8449",
                         arrowprops=dict(arrowstyle="->", color="#1E8449", lw=1.0))

    ax2_r = ax2.twinx()
    ax2_r.plot(hours, cum_ml, color="#D35400", marker="s", markersize=4.5, linewidth=2.0, label="Cumulative Intake (mL)")
    ax2_r.set_ylabel("Cumulative Health Connect Intake (mL)", fontsize=10, fontweight="bold", color="#D35400")
    ax2_r.tick_params(axis="y", labelcolor="#D35400")
    ax2_r.set_ylim(0, max(cum_ml) * 1.22)

    ax2.set_xlabel("Time of Day (Hours)", fontsize=10, fontweight="bold")
    ax2.set_ylabel("Stabilized Bottle Mass (g)", fontsize=10, fontweight="bold", color="#1F618D")
    ax2.tick_params(axis="y", labelcolor="#1F618D")
    ax2.set_ylim(250, 1380)
    ax2.set_xlim(6.0, 22.5)
    ax2.grid(True, linestyle="--", alpha=0.4)
    ax2.set_title(f"B. 24-Hr Pre/Post-Sip Delta Simulation (Logged = {int(cum_ml[-1])} mL)",
                  fontsize=10.8, fontweight="bold", color="#1B4F72")

    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_r.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8.5, frameon=True)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="#FFFFFF")
    plt.close(fig)


def main() -> None:
    print("=== HydroCap Power Budget Model (30 lifts/day: 100mAh 401520 [pet_30] & 150mAh 302030) ===")
    for p in PROFILES:
        r150 = compute_battery_metrics(p, battery_mah=150.0)
        r100 = compute_battery_metrics(p, battery_mah=100.0)
        print(
            f"{p.name:38s} | sleep={r150['sleep_ua']:6.1f} uA | "
            f"100mAh(pet_30)={r100['realistic_months']:4.1f} mo | "
            f"150mAh(302030)={r150['realistic_months']:4.1f} mo"
        )

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out_png = os.path.join(repo_root, "outputs", "power_budget_and_sip_simulation.png")
    generate_summary_figure(out_png)
    print(f"Saved power & simulation plot -> {out_png}")


if __name__ == "__main__":
    main()
