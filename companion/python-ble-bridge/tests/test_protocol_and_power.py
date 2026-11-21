import csv
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone

import ezdxf

BRIDGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.abspath(os.path.join(BRIDGE_DIR, "..", ".."))
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
    assert raw[:4] == b"\x2a\x00\x00\x00"
    assert HydrationEvent.decode(raw) == ev

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


def test_pcbway_manufacturing_package_integrity():
    pcbway_dir = os.path.join(REPO_ROOT, "hardware", "pcbway")
    zip_path = os.path.join(pcbway_dir, "fab", "HydroCap_V2_PCBWay_Gerbers.zip")
    assert os.path.isfile(zip_path)

    required_exts = (".GTL", ".G2", ".G3", ".GBL", ".GTS", ".GBS", ".GTO", ".GBO", ".GTP", ".GM1", "-PTH.drl", "-NPTH.drl")
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        for ext in required_exts:
            assert any(n.endswith(ext) for n in names), f"Missing Gerber/Drill layer {ext}"

    # Verify 1:1 designator parity between BOM and Pick-and-Place CPL
    bom_path = os.path.join(pcbway_dir, "pcba", "HydroCap_V2_PCBWay_BOM.csv")
    cpl_path = os.path.join(pcbway_dir, "pcba", "HydroCap_V2_PCBWay_CPL_PickAndPlace.csv")
    with open(bom_path, newline="", encoding="utf-8") as f:
        bom_refs = [row["Designator"] for row in csv.DictReader(f)]
    with open(cpl_path, newline="", encoding="utf-8") as f:
        cpl_rows = list(csv.DictReader(f))
        cpl_refs = [row["Designator"] for row in cpl_rows]
    assert bom_refs == cpl_refs and len(bom_refs) >= 18
    for row in cpl_rows:
        float(row["Mid X (mm)"])
        float(row["Mid Y (mm)"])

    # Verify KiCad 8 schematic & PCB files have balanced parentheses
    for fname in ("HydroCap_V2.kicad_sch", "HydroCap_V2.kicad_pcb"):
        fpath = os.path.join(pcbway_dir, "kicad", fname)
        assert os.path.isfile(fpath)
        txt = open(fpath, encoding="utf-8").read()
        assert txt.count("(") == txt.count(")") and txt.count("(") > 10


def test_split_stl_dxf_and_animation_assets():
    stl_dir = os.path.join(REPO_ROOT, "cad", "stl_print_parts")
    expected_stls = [
        "01_scroll_collar_knurled_u65.stl",
        "02_chuck_hub_plate_u65.stl",
        "03_gripper_jaw_x3.stl",
        "04_jaw_grip_pad_tpu_x3.stl",
        "05_upper_puck_housing_usbc_ip67.stl",
        "06_top_waterproof_lid.stl",
        "07_folding_finger_bail.stl",
        "08_usbc_waterproof_plug_tpu.stl",
    ]
    for f in expected_stls:
        p = os.path.join(stl_dir, f)
        assert os.path.isfile(p) and os.path.getsize(p) > 200

    dxf_path = os.path.join(stl_dir, "09_flexure_3spoke_0p8mm_301SS.dxf")
    doc = ezdxf.readfile(dxf_path)
    assert len(list(doc.modelspace())) >= 9

    gif_path = os.path.join(REPO_ROOT, "outputs", "hydrocap_attachment_animation.gif")
    mp4_path = os.path.join(REPO_ROOT, "outputs", "hydrocap_attachment_animation.mp4")
    assert os.path.isfile(gif_path) and 10_000 < os.path.getsize(gif_path) < 1_887_436
    assert os.path.isfile(mp4_path) and os.path.getsize(mp4_path) > 10_000


def test_wasm_kernel_and_dawn_pipeline():
    wasm_path = os.path.join(REPO_ROOT, "webgpu-dawn-wasm", "wasm", "hydrocap_kinematics.wasm")
    kf_sheet = os.path.join(REPO_ROOT, "outputs", "hydrocap_dawn_webgpu_keyframes.png")
    assert os.path.isfile(wasm_path) and os.path.getsize(wasm_path) > 200
    assert os.path.isfile(kf_sheet) and os.path.getsize(kf_sheet) > 10_000

    js_probe = (
        "const fs = require('fs');"
        "const bytes = fs.readFileSync(process.argv[1]);"
        "if (!WebAssembly.validate(bytes)) process.exit(2);"
        "const mem = new WebAssembly.Memory({ initial: 4 });"
        "WebAssembly.instantiate(bytes, { env: { __linear_memory: mem } }).then(({ instance }) => {"
        "  const f = new Float32Array(mem.buffer);"
        "  instance.exports.wasm_eval_stage(3.8, 12.0, 1024);"
        "  if (Math.round(f[256]) !== 2 || Math.round(f[256 + 9]) !== 1180) process.exit(3);"
        "  instance.exports.wasm_eval_physics(1067.0, 1.10, 1180.0, 2400);"
        "  if (Math.abs(f[600] - 970.0) > 0.5 || Math.abs(f[601] - 210.0) > 0.5) process.exit(4);"
        "});"
    )
    proc = subprocess.run(["node", "-e", js_probe, wasm_path], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"WASM probe failed: {proc.stderr}"


def test_1p1x_cap_ratio_and_compact_pcb_specs():
    # Verify Ø28.0 mm PCBWay core CPL coordinates fit strictly inside R=14.0 mm (except mid-mount USB-C J1)
    cpl_path = os.path.join(REPO_ROOT, "hardware", "pcbway", "pcba", "HydroCap_V2_PCBWay_CPL_PickAndPlace.csv")
    with open(cpl_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            x, y = float(row["Mid X (mm)"]), float(row["Mid Y (mm)"])
            assert (x * x + y * y) ** 0.5 < 13.5, f"{row['Designator']} outside compact Ø28mm core"

    # Verify universal Ø30.0 mm flexure DXF outer circle radius == 15.0 mm
    dxf_path = os.path.join(REPO_ROOT, "cad", "stl_print_parts", "09_flexure_3spoke_0p8mm_301SS.dxf")
    doc = ezdxf.readfile(dxf_path)
    outer_circles = [e for e in doc.modelspace() if e.dxftype() == "CIRCLE" and e.dxf.layer == "CUT_OUTER"]
    assert len(outer_circles) == 1 and abs(outer_circles[0].dxf.radius - 15.0) < 1e-3

    # Verify pet_30 1.1x STL dimensions (~33.6 mm OD)
    import trimesh
    stl_pet = os.path.join(REPO_ROOT, "cad", "outputs", "cap_gripper_pet_30_1p1x.stl")
    assert os.path.isfile(stl_pet)
    mesh = trimesh.load(stl_pet)
    dx, dy, _ = mesh.bounds[1] - mesh.bounds[0]
    assert 33.0 <= dx <= 36.0 and 33.0 <= dy <= 36.0
