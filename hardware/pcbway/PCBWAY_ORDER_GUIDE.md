# PCBWay Fabrication, Turnkey PCBA, 3D Printing & Sheet-Metal Order Guide

All manufacturing deliverables in this repository were generated from a single source of truth ([`generate_pcbway_package.py`](generate_pcbway_package.py)) and verified against PCBWay's Gerber, Drill, BOM, Pick-and-Place, and mechanical clearance rules.

---

## 1. Universal `Ø 28.0 mm` V2.1 PCB + SMT Assembly (`PCBWay Standard PCB + PCBA`)

One single **`Ø 28.0 mm`** circular PCB core drops cleanly into **every `1.1 × D_cap` HydroCap shell tier** (`33.6 mm` PET cap up to `69.3 mm` wide-mouth Nalgene/Hydro Flask).

### A. PCB Fabrication Quote Settings
* **Upload Gerber Archive:** [`hardware/pcbway/fab/HydroCap_V2_PCBWay_Gerbers.zip`](fab/HydroCap_V2_PCBWay_Gerbers.zip)
* **Board Dimensions:** Circular **`Ø 28.0 mm`** (`28 × 28 mm` bounding box)
* **Layers:** `4 Layers` (`GTL` Top, `G2` GND, `G3` 3V3, `GBL` Bottom)
* **Board Thickness:** **`0.8 mm`**
* **Surface Finish:** **ENIG (Immersion Gold) — RoHS**
* **Copper Weight:** `1 oz` outer / `0.5 oz` inner

### B. Turnkey PCBA Assembly Upload
* **BOM CSV:** [`hardware/pcbway/pcba/HydroCap_V2_PCBWay_BOM.csv`](pcba/HydroCap_V2_PCBWay_BOM.csv)
* **Centroid / Pick-and-Place CPL CSV:** [`hardware/pcbway/pcba/HydroCap_V2_PCBWay_CPL_PickAndPlace.csv`](pcba/HydroCap_V2_PCBWay_CPL_PickAndPlace.csv)
* **Assembly Side:** **Top Side Only (Single-Side SMT)** — all `17` active SMT components (`U1` `MDBT50Q`, `U2` `NAU7802YG` QFN-16, `U3` `BMA400`, `U4` `BQ25180`, `U5` `USBLC6`, `U6` `TPS7A0233`, `J1` IPX8 USB-C, `SW1`, `D1`, `R1–R5`, `C1–C6`) are Top-side. Bottom (`B.Cu`) has `PCB_PAD_DNP` pads only (`J2` `TC2030`, `J3` flexure bridge, `J4` `401520` LiPo).

---

## 2. Universal Sheet-Metal Laser Cutting (`PCBWay Sheet Metal`)

* **Upload DXF:** [`cad/stl_print_parts/09_flexure_3spoke_0p8mm_301SS.dxf`](../../cad/stl_print_parts/09_flexure_3spoke_0p8mm_301SS.dxf)
* **Dimensions:** **`Ø 30.0 mm`** outer ring × **`0.8 mm`** thickness *(fits all 4 `1.1 × D_cap` shells!)*
* **Material:** **`301 Stainless Steel (Full Hard)`** or `17-7PH` spring temper
* **Strain Gauges:** Bond `4× BF1000-2AA` / `BF1000-3AA` (`1000 Ω`) miniature gauges onto Spokes 1 & 2.

---

## 3. 3D Printing (`PCBWay 3D Printing` — `1.1 × D_cap` Shell Family)

Upload the split `.stl` parts from [`cad/stl_print_parts/`](../../cad/stl_print_parts/) (`pet_30` hero default: **`Ø 33.6 mm`** for `30.5 mm` PET bottle caps, or switch `CAP_TIER` in [`universal_cap_gripper.scad`](../../cad/universal_cap_gripper.scad) for `sport_40` `45.1 mm`, `flask_48` `52.8 mm`, or `wide_63` `69.3 mm`):

| File | Qty | Material | Purpose |
| :--- | :---: | :--- | :--- |
| `01_scroll_collar_knurled_u65.stl` | 1 | PA12 / PETG | Compression collar (`Ø 33.6 mm = 1.10 × 30.5 mm`) |
| `02_chuck_hub_plate_u65.stl` | 1 | PA12 / PETG | Inner flexure carrier + RTV wire gland |
| `03_gripper_jaw_x3.stl` | **3** | PA12 / PETG | Tapered lock wedges (or print `04_jaw_grip_pad_tpu_x3.stl` split collet) |
| `04_jaw_grip_pad_tpu_x3.stl` | **1** | **TPU 85A** | 6-petal compliant split silicone/TPU grip collet |
| `05_upper_puck_housing_usbc_ip67.stl` | 1 | PA12 / PETG | Houses `Ø 28.0 mm` PCB + `401520` LiPo + IPX8 USB-C bezel + O-ring groove |
| `06_top_waterproof_lid.stl` | 1 | PA12 / PETG | Compresses radial O-ring (`Ø 30.5 × 1.2 mm`) |
| `07_folding_finger_bail.stl` | 1 | PA12 / CF-PETG | Flush-folding bottle-lift bail (`Ø 32.8 mm`) |
| `08_usbc_waterproof_plug_tpu.stl` | 1 | **TPU 85A** | Captive IP67 USB-C washdown plug |
