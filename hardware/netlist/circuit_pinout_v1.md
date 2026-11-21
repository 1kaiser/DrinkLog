# Circuit Pinout & Wiring Guide (V1 Prototypes)

---

## 1. Primary V1: Seeed XIAO nRF52840 + NAU7802 + BMA400 + 4× BF1000-3AA

> **Expected Standby Current:** `~6.5 µA` (`~12 months` on `150 mAh` `302030` LiPo)

| XIAO nRF52840 Pin | Function / Net | Connected Component Pin | Electrical Notes |
| :--- | :--- | :--- | :--- |
| `3V3` | `VDD_3V3` | `NAU7802 DVDD/VDD`, `BMA400 VDD/VDDIO` | Regulated 3.3V from XIAO onboard regulator; add `100 nF` decoupling at each IC |
| `GND` | `GND` | `NAU7802 GND/AVSS`, `BMA400 GND/SDO` | Tie `BMA400 SDO` to `GND` to select I²C address `0x14` |
| `D4` (`P0.04`) | `I2C_SDA` | `NAU7802 SDA`, `BMA400 SDX` | `4.7 kΩ` pull-up to `3V3` (only one pull-up pair enabled on bus) |
| `D5` (`P0.05`) | `I2C_SCL` | `NAU7802 SCL`, `BMA400 SCX` | `4.7 kΩ` pull-up to `3V3` |
| `D1` (`P0.03`) | `IMU_INT1` | `BMA400 INT1` | Push-pull active-HIGH rising-edge motion wake interrupt |
| `D2` (`P0.28`) | `ADC_DRDY` | `NAU7802 DRDY` | Optional hardware DRDY (I²C polling also supported) |
| `BAT+` (Back Pad) | `VBAT` | `302030 LiPo +` (with PCM) | Charged at `~50–100 mA` via onboard `BQ25101` when USB-C is plugged in |
| `BAT-` (Back Pad) | `GND` | `302030 LiPo -` | Short heavy trace |
| `P0.14` (Internal) | `READ_BAT_ENABLE` | Internal MOSFET gate | Pull `LOW` ONLY for `1 ms` when reading `P0.31`, then drive `HIGH` to prevent divider drain |
| `P0.31` (Internal) | `VBAT_ADC` | Internal resistor divider | Measures `VBAT` (`× 3.0` divider scaling on XIAO nRF52840) |

### NAU7802 Analog Front-End & 1000 Ω Wheatstone Bridge Wiring
| NAU7802 Pin | Connection | Analog Filter / Value |
| :--- | :--- | :--- |
| `AVDD` / `REFP` | Bridge Excitation `+` (`E+`) + `1 µF` ceramic cap to `GND` | Software-programmed to `2.4 V`; turns **High-Z (OFF)** when `PUA=0, PUD=0` |
| `AGND` / `REFN` | Bridge Excitation `-` (`E-`) + `GND` | Star-ground analog return |
| `VIN1P` (`Ch1+`) | Bridge Output `+` (`S+`) | `100 nF` **C0G/NP0** differential cap across `VIN1P–VIN1N` + `10 nF` to `GND` |
| `VIN1N` (`Ch1-`) | Bridge Output `-` (`S-`) | Matched trace length to `VIN1P` |
| `VBG` | Bandgap reference bypass | `100 nF` X7R/C0G cap to `GND` |

**Bridge Leg Arrangement (4× `BF1000-3AA` `1000 Ω` on 3-Spoke Flexure):**
* `R1` (Tension, top spoke root) & `R3` (Tension, opposite spoke face): opposing bridge arms.
* `R2` (Compression, bottom spoke root) & `R4` (Compression, paired face): opposing bridge arms.
* Excitation current when active: `I_bridge = 2.4 V / 1000 Ω = 2.4 mA` (`0.00 µA` when sleeping).

---

## 2. Alternate V1A: TE FX29 I²C Sleep (`Ø 19.7 × 5.0 mm`, Zero Analog Wiring)

Omit `NAU7802`, filter caps, and strain gauges; connect the **FX29 I²C Sleep** variant (`FX29K0-100A-0010-L`, `0x28`) straight to the shared I²C bus:

| FX29 Pin | Net | XIAO nRF52840 Pin | Notes |
| :--- | :--- | :--- | :--- |
| `VCC` | `3V3` | `3V3` | `3.0–5.0 V` supply (`0.5 µA` sleep current) |
| `GND` | `GND` | `GND` | Common ground |
| `SDA` | `I2C_SDA` | `D4` (`P0.04`) | `4.7 kΩ` pull-up to `3V3` |
| `SCL` | `I2C_SCL` | `D5` (`P0.05`) | `4.7 kΩ` pull-up to `3V3` |

---

## 3. Alternate V1B: XIAO nRF52840 Sense (Onboard `LSM6DS3TR-C`, Zero-Wire IMU)

* Uses the exact `NAU7802` or `FX29` connections above on `D4/D5`, with **no external `BMA400`**.
* **Mandatory Register Settings (Avoids `~200 µA` Sleep Trap):**
  * `CTRL2_G (0x11) = 0x00` → Power down gyroscope completely.
  * `CTRL1_XL (0x10) = 0x10` + `CTRL6_C (0x15) = 0x10` → `12.5 Hz` low-power accelerometer (`~35–50 µA`).
  * Route `WAKE_UP` interrupt (`MD1_CFG = 0x20`) to internal `INT1` (`PIN_LSM6DS3TR_C_INT1`).

---

## 4. Alternate V1C: Budget XIAO ESP32-C6 (`~$6` MCU)

| XIAO ESP32-C6 Pin | Net | Connected Component | Notes |
| :--- | :--- | :--- | :--- |
| `3V3` / `GND` | Power | `NAU7802` + `BMA400` | Never call `WiFi.begin()`; keep Wi-Fi/802.15.4 disabled (`~15–20 µA` deep sleep) |
| `D4` (`GPIO22`) | `I2C_SDA` | `NAU7802 SDA`, `BMA400 SDX` | `4.7 kΩ` pull-up |
| `D5` (`GPIO23`) | `I2C_SCL` | `NAU7802 SCL`, `BMA400 SCX` | `4.7 kΩ` pull-up |
| `D1` (`GPIO1`) | `IMU_INT1` | `BMA400 INT1` | `esp_deep_sleep_enable_gpio_wakeup(BIT(1), ESP_GPIO_WAKEUP_GPIO_HIGH)` (LP GPIO `0..7`) |
| `BAT+` / `BAT-` | `VBAT` | `302030 LiPo` | Backside solder pads |
