# CapHydro — Ultra-Thin Universal Bottle-Cap Hydration Tracker

An open-hardware, ultra-low-power, rechargeable **Bluetooth Low Energy (BLE)** bottle-cap add-on that measures consumed fluid via pre/post-sip gravimetric weight differences and syncs directly to **Android Health Connect** (`HydrationRecord`).

---

## Core Physics & Engineering Rules

1. **Cap-Lift Load Path (`100%` Mass Coupling):**
   When a bottle sits on a table—or is lifted by its body—the cap bears zero weight. CapHydro integrates a **flush-folding finger bail & outer lift collar** on top of a **universal 3-jaw scroll-chuck gripper (`26–65 mm` cap OD)** so lifting the bottle by its cap routes 100% of gravitational weight through the thin sensing stage.
2. **Screw-Cap Pre/Post Delta Algorithm (Not Mid-Sip Tilt):**
   Because a screw-on cap is removed while drinking, each cap-lift records a timestamped stabilized mass $m_k$:
   $$\Delta V_{\text{mL}} = \frac{m_{k-1} - m_k}{\rho}, \qquad \rho_{\text{water}} \approx 1.00\text{ g/mL}$$
   * **$\Delta m \ge +15\text{ g}$:** Logged as **fluid consumed** (`delta_ml > 0`).
   * **$\Delta m \le -25\text{ g}$:** Classified as a **bottle refill** (`delta_ml = 0`, updates baseline mass).
   * **`|m| < 45 g` (Unscrewed Cap Auto-Tare):** When the cap is unscrewed and unweighted, firmware smoothly updates the zero-offset via EMA (`0.8 * old + 0.2 * new`), cancelling long-term strain-gauge drift automatically.
3. **Moment-Cancelling Flexure + Inertial Compensation:**
   A **0.8 mm 301-SS 3-spoke (120°) annular flexure** with mechanical overload hard-stops (`0.35 mm`) and `4× BF1000-3AA` (`1000 Ω`) full Wheatstone bridge cancels tilt bending moments ($M_x, M_y$) and unscrewing torque ($T_z$). During gentle vertical holds (`|ω| < 5 °/s`, tilt `< 15°`), axial inertial error is removed via:
   $$m = \frac{F_z}{a_z}, \qquad a_z \in [0.85g,\,1.15g]$$
4. **Zero-Leakage Bridge Power Gating:**
   Using **Nuvoton NAU7802** (24-bit I²C ADC) with its internal `AVDD` LDO (`2.4 V`) switched to **High-Z** in power-down eliminates 100% of static bridge current between lifts (`0 µA` bridge draw, `< 1 µA` ADC sleep). Combined with **Bosch BMA400** (`~0.9 µA` auto-wake) and **Seeed XIAO nRF52840**, total system standby is **`~6.5 µA`** (~12 months on a `3.0 mm` thick `150 mAh` `302030` LiPo).

---

## Project Layout

```text
cap-hydration-tracker/
├── docs/
│   ├── DESIGN_SPEC.md                 # Physics, MCU comparison, BLE GATT spec, power math
│   └── BOM.csv                        # Multi-variant BOM (V1 FX29, V1 DIY Flexure, ESP32-C6, V2 PCB)
├── hardware/
│   ├── netlist/
│   │   ├── circuit_pinout_v1.md       # Pin-to-pin tables (XIAO nRF52840, Sense, ESP32-C6, FX29)
│   │   └── schematic_v2_custom_pcb.net# KiCad logical netlist for Ø40 mm 0.8 mm custom PCB
│   └── diagrams/
│       ├── generate_diagrams.py       # Generates zero-overlap .drawio XML + crisp PNG renders
│       ├── system_circuit_schematic.{drawio,png}
│       └── firmware_ble_pipeline.{drawio,png}
├── cad/
│   ├── universal_cap_gripper.scad     # Parametric OpenSCAD (26-65 mm / 26-45 mm, flexure / FX29)
│   ├── generate_cad_assets.py         # Trimesh STL/GLB generator + 4-panel orthographic drawing
│   └── outputs/
│       ├── cap_gripper_universal_65.{stl,glb}
│       ├── cap_gripper_compact_45.glb
│       └── mechanical_orthographic_views.png
├── firmware/
│   ├── platformio.ini                 # 3 MCU envs (nRF52840+BMA400, nRF52840 Sense, ESP32-C6) + native
│   ├── include/
│   │   ├── config.h                   # Pin maps, GATT UUIDs, physical thresholds
│   │   ├── hydration_core.h           # Pure C++17 DSP, auto-tare, sip classifier, 64-event ring
│   │   └── sensor_drivers.h           # HAL for NAU7802, TE FX29 I2C, BMA400, LSM6DS3TR-C
│   ├── src/
│   │   ├── main_nrf52.cpp             # Bluefruit BLE + __WFE() sleep + P0.14/P0.31 VBAT monitor
│   │   └── main_esp32c6.cpp           # NimBLE + Wi-Fi off + RTC_DATA_ATTR deep sleep retention
│   └── tests/
│       └── test_hydration_core.cpp    # Native C++17 unit test suite
├── companion/
│   ├── android-health-connect/        # Kotlin Jetpack Health Connect HydrationRecord client
│   └── python-ble-bridge/             # bleak BLE receiver, simulator, power model & pytest suite
└── outputs/
    └── power_budget_and_sip_simulation.png
```

---

## Quickstart & Verification Commands

### 1. Compile & Run Native C++17 Firmware Unit Tests
```bash
g++ -std=c++17 -Wall -Wextra -Werror -Ifirmware/include \
  firmware/tests/test_hydration_core.cpp -o /tmp/test_hydration_core && /tmp/test_hydration_core
```

### 2. Run Python Protocol, Power Model & Offline BLE Loopback Tests
```bash
/home/kaiser/.miniforge/envs/num_python/bin/python companion/python-ble-bridge/power_budget_model.py
/home/kaiser/.miniforge/envs/num_python/bin/python companion/python-ble-bridge/cap_ble_receiver.py --simulate
/home/kaiser/.miniforge/envs/num_python/bin/python -m pytest -v companion/python-ble-bridge/tests/
```

### 3. Generate Diagrams & Audit Draw.io Geometry (0 Overlaps)
```bash
/home/kaiser/.miniforge/envs/num_python/bin/python hardware/diagrams/generate_diagrams.py
/home/kaiser/.miniforge/envs/num_python/bin/python /home/kaiser/.gemini/config/skills/drawio-headless-rendering/scripts/analyze_drawio_overlap.py hardware/diagrams/system_circuit_schematic.drawio
/home/kaiser/.miniforge/envs/num_python/bin/python /home/kaiser/.gemini/config/skills/drawio-headless-rendering/scripts/analyze_drawio_overlap.py hardware/diagrams/firmware_ble_pipeline.drawio
```

### 4. Generate 3D CAD Meshes (`.stl`, `.glb`) & Orthographic Engineering Drawing
```bash
/home/kaiser/.miniforge/envs/num_python/bin/python cad/generate_cad_assets.py
```

### 5. Build & Flash MCU Firmware (PlatformIO)
```bash
cd firmware
pio run -e xiao_nrf52840_bma400 -t upload   # Primary (~12 mo battery)
# pio run -e xiao_nrf52840_sense -t upload  # Zero-wiring V1 Sense (~3-4 mo battery)
# pio run -e xiao_esp32c6_bma400 -t upload  # Budget ~$6 MCU (~5-6 mo battery)
```
