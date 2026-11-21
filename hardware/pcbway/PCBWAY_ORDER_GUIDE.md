# PCBWay Fabrication, Turnkey PCBA, 3D Printing & Sheet-Metal Order Guide

All manufacturing deliverables in this repository were generated from a single source of truth ([`generate_pcbway_package.py`](generate_pcbway_package.py)) and formatted to pass PCBWay's automated Gerber, Drill, BOM, and Pick-and-Place checks.

---

## 1. Custom V2 PCB + SMT Assembly (`PCBWay Standard PCB + PCBA`)

### A. PCB Fabrication Quote Settings
* **Upload Gerber Archive:** [`hardware/pcbway/fab/HydroCap_V2_PCBWay_Gerbers.zip`](fab/HydroCap_V2_PCBWay_Gerbers.zip)
* **Board Dimensions:** Circular `Ø 42.0 mm` (`42 × 42 mm` bounding box)
* **Layers:** `4 Layers` (`GTL` Top, `G2` GND, `G3` 3V3, `GBL` Bottom)
* **Board Thickness:** **`0.8 mm`** *(critical for ultra-thin puck stackup & mid-mount USB-C pocket)*
* **Surface Finish:** **ENIG (Immersion Gold) — RoHS** *(mandatory for flat bottom `TC2030` SWD pogo pads & `0.4 mm` USB-C pitch)*
* **Copper Weight:** `1 oz` outer / `0.5 oz` inner
* **Solder Mask / Silkscreen:** Green or Matte Black / White

### B. Turnkey PCBA Assembly Upload
* **BOM CSV:** [`hardware/pcbway/pcba/HydroCap_V2_PCBWay_BOM.csv`](pcba/HydroCap_V2_PCBWay_BOM.csv)
* **Centroid / Pick-and-Place CPL CSV:** [`hardware/pcbway/pcba/HydroCap_V2_PCBWay_CPL_PickAndPlace.csv`](pcba/HydroCap_V2_PCBWay_CPL_PickAndPlace.csv)
* **Assembly Side:** **Top Side Only (Single-Side SMT)** — all `17` active ICs/passives (`U1`–`U6`, `J1`, `SW1`, `D1`, `R1`–`R5`, `C1`–`C6`) sit on the Top (`F.Cu`) layer. Bottom (`B.Cu`) contains copper-only `PCB_PAD_DNP` footprints (`J2` Tag-Connect `TC2030`, `J3` Strain Bridge pads, `J4` `302030` LiPo pads) requiring zero SMT placement.
* **Special Note for PCBWay Engineer:**
  > *"Board uses mid-mount IPX8 USB-C `12402448E512A` (`J1`) and keep-out PCB antenna on `MDBT50Q-1MV2` (`U1`) at `+Y` perimeter. Do not place solder paste or components on `J2`, `J3`, `J4` (Bottom PCB_PAD_DNP)."*

---

## 2. Sheet-Metal Laser Cutting (`PCBWay Sheet Metal`)

* **Upload DXF:** [`cad/stl_print_parts/09_flexure_3spoke_0p8mm_301SS.dxf`](../../cad/stl_print_parts/09_flexure_3spoke_0p8mm_301SS.dxf)
* **Material:** **`301 Stainless Steel (Full Hard)`** *(or `17-7PH` spring temper)*
* **Thickness:** **`0.8 mm`**
* **Process:** Fiber Laser Cutting (deburred, no bending)
* **Post-Step:** Bond `4× BF1000-3AA` (`1000 Ω`) strain gauges along top/bottom faces of Spokes 1 & 2 with M-Bond 200 / Loctite 401 cyanoacrylate and protect with neutral-cure silicone RTV.

---

## 3. 3D Printing (`PCBWay 3D Printing` or Local FDM / SLA)

Upload the split `.stl` parts from [`cad/stl_print_parts/`](../../cad/stl_print_parts/):

| File | Qty | Recommended Material / Process | Purpose |
| :--- | :---: | :--- | :--- |
| `01_scroll_collar_knurled_u65.stl` | 1 | PA12 Nylon (MJF) or PETG (FDM, 0.16 mm) | Outer scroll ring clamping `26–65 mm` caps |
| `02_chuck_hub_plate_u65.stl` | 1 | PA12 Nylon or PETG | 3-slot radial jaw carrier |
| `03_gripper_jaw_x3.stl` | **3** | PA12 Nylon or PETG | Concentric gripping jaws |
| `04_jaw_grip_pad_tpu_x3.stl` | **3** | **TPU 85A** (or cast Shore-40A silicone) | High-friction cap contact pads |
| `05_upper_puck_housing_usbc_ip67.stl` | 1 | PA12 Nylon or PETG + silicone conformal coat | Holds PCB, `302030` LiPo, IPX8 USB-C bezel & O-ring |
| `06_top_waterproof_lid.stl` | 1 | PA12 Nylon or PETG | Compresses radial O-ring (`Ø 58 × 1.5 mm`) |
| `07_folding_finger_bail.stl` | 1 | PA12 Nylon or CF-PETG | Flush-folding bottle-lift bail |
| `08_usbc_waterproof_plug_tpu.stl` | 1 | **TPU 85A** | Secondary captive IP67 USB-C dust/water seal plug |
