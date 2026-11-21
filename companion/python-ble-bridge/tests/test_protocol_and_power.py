import os
import sys
from datetime import datetime, timedelta, timezone

BRIDGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BRIDGE_DIR not in sys.path:
    sys.path.insert(0, BRIDGE_DIR)

from cap_ble_receiver import run_offline_simulation
from power_budget_model import PROFILES, compute_battery_metrics
from protocol import (
    DeviceStatus,
    HydrationEvent,
    decode_ack,
    encode_ack,
    reconstruct_timestamp,
    simulate_24h_bottle_day,
)


def test_binary_struct_parity():
    ev = HydrationEvent(seq=42, uptime_s=86415, delta_ml=210, bottle_mass_g=790)
    raw = ev.encode()
    assert len(raw) == 12
    # seq=42 LE: 2a 00 00 00
    assert raw[:4] == b"\x2a\x00\x00\x00"
    decoded = HydrationEvent.decode(raw)
    assert decoded == ev

    st = DeviceStatus(device_uptime_s=100000, vbat_mv=4120, last_mass_g=790)
    st_raw = st.encode()
    assert len(st_raw) == 8
    assert DeviceStatus.decode(st_raw) == st

    ack_raw = encode_ack(42)
    assert len(ack_raw) == 4
    assert decode_ack(ack_raw) == 42


def test_offline_timestamp_reconstruction():
    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)
    ts = reconstruct_timestamp(now, device_uptime_s=5000, event_uptime_s=4400)
    assert ts == now - timedelta(seconds=600)


def test_24h_simulation_ignores_refills_and_jitter():
    events = simulate_24h_bottle_day()
    # 1 baseline + 9 sips + 2 refills = 12 events (jitter 970 -> 963 excluded)
    assert len(events) == 12
    total_ml = sum(e.delta_ml for e in events)
    assert total_ml == (210 + 225 + 185 + 150 + 230 + 220 + 210 + 230 + 170)


def test_power_budget_ordering_and_bounds():
    by_name = {p.name: compute_battery_metrics(p) for p in PROFILES}
    nrf = by_name["XIAO nRF52840 + BMA400 (Primary V1)"]
    sense = by_name["XIAO nRF52840 Sense (LSM6DS3 LP)"]
    esp_c6 = by_name["XIAO ESP32-C6 + BMA400 (Budget)"]
    rp2040 = by_name["XIAO RP2040 + Ext BLE (No LP RTC)"]

    assert nrf["sleep_ua"] < 8.0
    assert nrf["realistic_months"] >= 9.0
    assert nrf["realistic_days"] > esp_c6["realistic_days"] > sense["realistic_days"] > rp2040["realistic_days"]
    assert rp2040["realistic_days"] < 15.0


def test_offline_cli_loopback(tmp_path):
    csv_out = tmp_path / "sim_log.csv"
    records = run_offline_simulation(str(csv_out))
    assert csv_out.exists()
    assert len(records) == 12
    assert all(r["ack_ok"] for r in records)
