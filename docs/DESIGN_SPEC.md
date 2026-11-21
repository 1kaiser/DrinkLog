# CapHydro — Hardware, Mechanical & Firmware Design Specification

## 1. System Objectives & Physical Constraints

| Requirement | Target Value | Design Solution |
| :--- | :--- | :--- |
| Added Cap Height | `7.5–11.0 mm` | Stacked pancake architecture (`0.8 mm` flexure + `4.0 mm` LiPo + `0.8 mm` PCB + housing) |
| Outer Diameter Ratio | **`1.10 × D_cap`** | 4-tier proportional shells (`33.6 mm` PET / `45.1 mm` Sport / `52.8 mm` Flask / `69.3 mm` Wide) |
| Universal Electronics Core | **`Ø 28.0 mm` PCB + `Ø 30.0 mm` Flexure** | Single PCBWay PCBA & laser-cut flexure drops into every `1.1×` shell tier |
| Bottle Mass Range | `45 g` to `4,500 g` | `1000 Ω` full bridge (`NAU7802YG` 24-bit QFN-16) or `TE FX29` (`10 lbf / 4.5 kg`) |
| Sip Resolution | `±5 mL` (`±5 g`) | 15-sample median filter + `m = F_z / a_z` inertial correction + cap-off auto-tare |
| Standby Power | `~6.5 µA` (`V1`), `< 4 µA` (`V2`) | `XIAO nRF52840` + `BMA400` (`0.9 µA`) + `NAU7802` High-Z `AVDD` gate (`0 µA` bridge off) |
| Battery Life | `~12 months` / charge (`150 mAh` `302030`) | Event-driven wake (`30 lifts/day × 1.2 s` active) + 64-event non-volatile ring buffer |
| Health Sync | Android **Health Connect** (`HydrationRecord`) | Idempotent `clientRecordId = "caphydro-{MAC}-{seq}"` + reliable BLE ACK clearing |

---

## 2. Mechanical Stackup & Load-Path Isolation

### Why a Top-Mounted Gripper Requires an Outer Lift Bail
A cap sensor cannot measure bottle mass while the bottle rests on a desk or is gripped by its cylindrical wall. The CapHydro puck places the **load-sensing flexure strictly between**:
1. **Bottom Frame (Bottle-Side):** 3-jaw scroll-chuck clamp gripped tightly onto the bottle screw cap (`26–65 mm` OD).
2. **Top Frame (Hand-Side):** Flush-folding pivoted finger bail and chamfered outer lift rim.

When the user lifts the bottle by the bail or outer lift collar, **100% of bottle weight** passes axially through the sensing stage.

### Mechanical Overload Protection & Moment Cancellation
* **3-Spoke 120° Planar Annular Flexure (`0.8 mm` 301-SS / 17-7PH):**
  Three symmetric radial beams spaced `120°` apart connect the inner cap-clamp hub to the outer lift ring. Wiring four `BF1000-3AA` (`1000 Ω`) strain gauges across opposing tension/compression faces in a full Wheatstone bridge:
  * **Doubles sensitivity** (`4×` quarter-bridge output) and **cancels ambient temperature drift**.
  * **Rejects off-axis tilt moments** ($M_x, M_y$) and cap twisting torque ($T_z$) by symmetric averaging.
* **Hard-Stop Gap (`0.35 mm`):** Bosses under the outer lift rim contact the inner hub shelf once deflection reaches `0.35 mm` (~`5 kg` load), preventing plastic yield if the bottle is dropped.
* **Alternative Off-the-Shelf Sensor (`TE FX29 I²C`):** `Ø 19.7 × 5.0 mm` factory-calibrated 14-bit compression cell mounted in a pull-to-compress reverse yoke (`~0.28 g/LSB`, `0.5 µA` sleep).

---

## 3. MCU & Platform Selection Matrix

| Platform | SoC & Radio | Board Size (mm) | Verified Sleep Floor | Wake IMU | Est. Battery (`150 mAh`, 30 lifts/d) | Decision |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Adafruit SHT4x Trinkey** | `ATSAMD21E18` (No BLE) | `30 × 12 × 3` | N/A (USB host only) | None | N/A | **Incompatible** (no wireless, no battery charger) |
| **XIAO RP2040 / Pico W** | `RP2040` (+ `CYW43439`) | `21 × 17.5` / `51 × 21` | `~500–1,500 µA` | None | `4–10 days` | **Disqualified** (no `<5 µA` RTC domain) |
| **Seeed XIAO ESP32-C3** | `ESP32-C3` (BLE 5.0) | `21 × 17.5 × 3.5` | `~41–45 µA` (LDO floor) | Ext `BMA400` | `~75–95 days` | Superseded by ESP32-C6 |
| **Seeed XIAO ESP32-C6** | `ESP32-C6` (BLE 5.3) | `21 × 17.5 × 3.5` | `~15–20 µA` (Wi-Fi off) | Ext `BMA400` | `~160–190 days` | **Budget Option (~\$6)** |
| **XIAO nRF52840 Sense** | `nRF52840` (BLE 5.0) | `21 × 17.5 × 3.5` | `~35–50 µA` (gyro OFF, 12.5 Hz) | Onboard `LSM6DS3TR-C` | `~95–125 days` | **Fastest Zero-Wire V1** |
| **XIAO nRF52840 + BMA400** | `nRF52840` (BLE 5.0) | `21 × 17.5 × 3.5` | **`~6.5 µA`** total | Ext `BMA400` (`0.9 µA`) | **`~365–488 days`** | **Primary V1 Recommendation** |
| **Custom nRF54L15 PCB** | `nRF54L15` (BLE 6.0) | `Ø 40 × 0.8` | **`< 4.0 µA`** (`BQ25180` + `BMA400`) | On-PCB `BMA400` | **`~540+ days`** | **V2 Production Target** |

---

## 4. BLE GATT Protocol Specification

* **Advertised Name:** `CapHydro`
* **Custom Hydration Service UUID:** `7a4b0001-3c9e-4f1a-9b2d-8e5c10293847`
* **Standard Battery Service:** `0x180F` → Battery Level Characteristic `0x2A19` (`uint8`, `0–100%`)

| Characteristic | UUID | Properties | Size | Little-Endian Binary Layout | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Hydration Event** | `7a4b0002-3c9e-4f1a-9b2d-8e5c10293847` | `NOTIFY \| READ` | `12 B` | `<IIhH`: `uint32 seq`, `uint32 uptime_s`, `int16 delta_ml`, `uint16 bottle_mass_g` | Pushed sequentially while `acked_seq < head_seq`. `delta_ml > 0` = sip; `delta_ml == 0` = baseline/refill snapshot. |
| **Event ACK** | `7a4b0003-3c9e-4f1a-9b2d-8e5c10293847` | `WRITE \| WRITE_NO_RESP` | `4 B` | `<I`: `uint32 last_acked_seq` | Written by phone **only after** Health Connect confirms `insertRecords()` success. |
| **Device Status** | `7a4b0004-3c9e-4f1a-9b2d-8e5c10293847` | `READ` | `8 B` | `<IHH`: `uint32 device_uptime_s`, `uint16 vbat_mv`, `uint16 last_mass_g` | Allows phone to map `ev.uptime_s` to wall-clock time (`sipEnd = now - (deviceUptimeS - ev.uptime_s)`). |

### Google Health Connect Mapping (Android 14+ / Jetpack `connect-client`)
* Legacy **Google Fit APIs** closed new sign-ups May 2024 and reach end-of-service in late 2026.
* Android writes `androidx.health.connect.client.records.HydrationRecord` with:
  * `volume = Volume.milliliters(deltaMl.toDouble())`
  * `metadata = Metadata.autoRecorded(device = Device(type = Device.TYPE_UNKNOWN), clientRecordId = "caphydro-$mac-$seq")`
  * Deduplication via `clientRecordId` ensures re-transmitted BLE packets never double-count fluid intake.

---

## 5. Power Budget Breakdown (`XIAO nRF52840 + BMA400 + NAU7802 + 1000 Ω Bridge`)

Assuming a `150 mAh` `302030` LiPo (`120 mAh` usable at `80%` depth-of-discharge) and **30 cap lifts/day**:

1. **Standby Draw (`23 h 59 m 24 s / day`):**
   * `XIAO nRF52840` System-ON idle + RTC/RAM: `5.0 µA`
   * `Bosch BMA400` (`25 Hz` auto-wake): `0.9 µA`
   * `Nuvoton NAU7802` (`PUA=0, PUD=0`, `AVDD=Hi-Z`): `0.5 µA` (`0.0 µA` bridge leakage)
   * **Total Standby:** `6.4 µA × 24 h = 0.1536 mAh/day`
2. **Active Event Draw (`30 events/day × 1.2 s`):**
   * Bridge excitation (`2.4 V / 1000 Ω = 2.4 mA`) + `NAU7802` active (`1.6 mA`) for `0.6 s`: `2.40 mA·s`
   * `nRF52840` wake & DSP (`5.0 mA × 1.2 s`): `6.00 mA·s`
   * BLE `0 dBm` notify burst (`8.0 mA × 0.3 s`): `2.40 mA·s`
   * **Per Event:** `10.8 mA·s = 0.0030 mAh` → **30 events/day = `0.090 mAh/day`**
3. **Total Daily Consumption:** `0.1536 + 0.090 = 0.2436 mAh/day`
   * Theoretical runtime (`120 mAh / 0.2436 mAh/day`): **~493 days**
   * Real-world runtime (accounting for ~2%/month LiPo self-discharge & occasional BLE resync retries): **~12 months per charge**.

---

## 6. Two-Point Calibration Procedure

1. Unscrew cap from bottle; hold level and motionless for 2 seconds while firmware records `zero_offset`.
2. Attach a known `500.0 g` calibration weight to the gripper/bail, lift vertically, and read raw ADC delta $\Delta C$.
3. Compute `SCALE_CAL_FACTOR = ΔC / 500.0f` (`counts/g`) and flash in `firmware/include/config.h`.
4. Verify with `200 g`, `500 g`, and `1000 g` test masses; confirm error `< ±2.0 g` (`±2 mL`).
