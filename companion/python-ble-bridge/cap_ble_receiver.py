#!/usr/bin/env python3
"""
Desktop/Linux BLE GATT receiver for DrinkLog (using bleak) with an offline
--simulate mode for testing the binary codec, Health Connect payload mapping,
and ACK flow without physical BLE hardware.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
from datetime import datetime, timezone
from typing import List

from protocol import (
    CHR_ACK_UUID,
    CHR_EVENT_UUID,
    CHR_STATUS_UUID,
    DeviceStatus,
    HydrationEvent,
    decode_ack,
    encode_ack,
    reconstruct_timestamp,
    simulate_24h_bottle_day,
)


def run_offline_simulation(csv_path: str) -> List[dict]:
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    sync_now = datetime.now(timezone.utc)
    sim_events = simulate_24h_bottle_day()
    sim_status = DeviceStatus(device_uptime_s=22 * 3600, vbat_mv=4085, last_mass_g=sim_events[-1].bottle_mass_g)
    raw_status = sim_status.encode()
    decoded_status = DeviceStatus.decode(raw_status)

    records: List[dict] = []
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_iso", "seq", "uptime_s", "bottle_mass_g", "delta_ml", "ack_verified", "vbat_mv"])

        for ev in sim_events:
            # Binary wire roundtrip test
            wire_bytes = ev.encode()
            rx = HydrationEvent.decode(wire_bytes)
            ts = reconstruct_timestamp(sync_now, decoded_status.device_uptime_s, rx.uptime_s)
            ack_wire = encode_ack(rx.seq)
            ack_seq = decode_ack(ack_wire)

            writer.writerow([ts.isoformat(), rx.seq, rx.uptime_s, rx.bottle_mass_g, rx.delta_ml, ack_seq == rx.seq, decoded_status.vbat_mv])
            records.append({
                "seq": rx.seq,
                "delta_ml": rx.delta_ml,
                "bottle_mass_g": rx.bottle_mass_g,
                "timestamp": ts.isoformat(),
                "ack_ok": ack_seq == rx.seq,
            })

    total_ml = sum(r["delta_ml"] for r in records if r["delta_ml"] > 0)
    print(f"[SIMULATE] Processed {len(records)} BLE packets | Total fluid consumed = {total_ml} mL")
    print(f"[SIMULATE] Health Connect CSV log written -> {csv_path}")
    return records


async def run_live_ble(csv_path: str, timeout_s: float = 15.0) -> None:
    try:
        from bleak import BleakClient, BleakScanner
    except ImportError as exc:
        raise RuntimeError(
            "The 'bleak' package is required for live BLE scanning. "
            "Install via 'pip install bleak' or run with '--simulate'."
        ) from exc

    dev = await BleakScanner.find_device_by_name("DrinkLog", timeout=timeout_s)
    if dev is None:
        print("DrinkLog not found; lift bottle by its cap to wake BLE advertising.")
        return

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    sync_now = datetime.now(timezone.utc)

    async with BleakClient(dev) as client:
        status_bytes = await client.read_gatt_char(CHR_STATUS_UUID)
        status = DeviceStatus.decode(bytes(status_bytes))
        print(f"Connected to {dev.address} | VBAT={status.vbat_mv} mV | Last={status.last_mass_g} g")

        async def on_event(_, data: bytearray) -> None:
            ev = HydrationEvent.decode(bytes(data))
            ts = reconstruct_timestamp(sync_now, status.device_uptime_s, ev.uptime_s)
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([ts.isoformat(), ev.seq, ev.uptime_s, ev.bottle_mass_g, ev.delta_ml, True, status.vbat_mv])
            print(json.dumps({"seq": ev.seq, "delta_ml": ev.delta_ml, "mass_g": ev.bottle_mass_g, "ts": ts.isoformat()}))
            await client.write_gatt_char(CHR_ACK_UUID, encode_ack(ev.seq), response=False)

        await client.start_notify(CHR_EVENT_UUID, on_event)
        await asyncio.sleep(10.0)


def main() -> None:
    default_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "hydration_log.csv")
    parser = argparse.ArgumentParser(description="DrinkLog BLE Hydration Receiver")
    parser.add_argument("--simulate", action="store_true", help="Run offline binary protocol loopback simulation")
    parser.add_argument("--csv", default=default_csv, help="Output CSV path")
    parser.add_argument("--timeout", type=float, default=15.0, help="BLE scan timeout (seconds)")
    args = parser.parse_args()

    if args.simulate:
        run_offline_simulation(args.csv)
    else:
        asyncio.run(run_live_ble(args.csv, args.timeout))


if __name__ == "__main__":
    main()
