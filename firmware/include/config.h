#pragma once
#include <cstdint>

namespace caphydro {

// ---------------------------------------------------------------------------
// BLE GATT Identifiers (Custom Hydration Service + Standard Battery Service)
// ---------------------------------------------------------------------------
static constexpr const char* BLE_DEVICE_NAME   = "CapHydro";
static constexpr const char* SVC_HYDRATION_UUID = "7a4b0001-3c9e-4f1a-9b2d-8e5c10293847";
static constexpr const char* CHR_EVENT_UUID     = "7a4b0002-3c9e-4f1a-9b2d-8e5c10293847";
static constexpr const char* CHR_ACK_UUID       = "7a4b0003-3c9e-4f1a-9b2d-8e5c10293847";
static constexpr const char* CHR_STATUS_UUID    = "7a4b0004-3c9e-4f1a-9b2d-8e5c10293847";

// ---------------------------------------------------------------------------
// I2C Addresses
// ---------------------------------------------------------------------------
static constexpr uint8_t I2C_ADDR_NAU7802 = 0x2A;
static constexpr uint8_t I2C_ADDR_FX29    = 0x28;
static constexpr uint8_t I2C_ADDR_BMA400  = 0x14; // SDO tied to GND
static constexpr uint8_t I2C_ADDR_LSM6DS3 = 0x6A; // Onboard XIAO Sense IMU

// ---------------------------------------------------------------------------
// Board-Specific Hardware Pin Mapping
// ---------------------------------------------------------------------------
#if defined(MCU_XIAO_NRF52840) || defined(MCU_XIAO_NRF52840_SENSE)
  static constexpr uint8_t PIN_IMU_INT1     = D1;     // External BMA400 INT1
  static constexpr uint8_t PIN_ADC_DRDY     = D2;     // Optional NAU7802 DRDY
  static constexpr uint8_t PIN_I2C_SDA      = D4;
  static constexpr uint8_t PIN_I2C_SCL      = D5;
  // XIAO nRF52840 internal VBAT sense pins (Nordic P0.14 & P0.31)
  static constexpr uint8_t PIN_VBAT_ENABLE  = 14;     // P0.14 LOW = enable divider
  static constexpr uint8_t PIN_VBAT_ADC     = 31;     // P0.31 analog input
#elif defined(MCU_XIAO_ESP32C6)
  static constexpr uint8_t PIN_IMU_INT1     = 1;      // GPIO1 (LP wakeup domain)
  static constexpr uint8_t PIN_ADC_DRDY     = 2;      // GPIO2
  static constexpr uint8_t PIN_I2C_SDA      = 22;     // D4
  static constexpr uint8_t PIN_I2C_SCL      = 23;     // D5
  static constexpr uint8_t PIN_VBAT_ADC     = 0;      // GPIO0 external 1:2 divider
#endif

// ---------------------------------------------------------------------------
// Gravimetric Physics & Classifier Calibration Constants
// ---------------------------------------------------------------------------
static constexpr float    DEFAULT_SCALE_COUNTS_PER_G = 420.5f;  // Calibrate w/ 500 g mass
static constexpr float    MIN_BOTTLE_MASS_G          = 45.0f;   // Below this => cap unscrewed (auto-tare)
static constexpr float    SIP_THRESHOLD_G            = 15.0f;   // Min drop to log fluid consumption
static constexpr float    REFILL_THRESHOLD_G         = -25.0f;  // Mass jump <= -25 g => refill event
static constexpr float    MAX_VALID_BOTTLE_G         = 4500.0f; // 4.5 kg upper clamp
static constexpr float    WATER_DENSITY_G_PER_ML     = 1.00f;
static constexpr float    AUTO_TARE_EMA_ALPHA        = 0.20f;

// Inertial & Tilt Safety Window (Static Vertical Hold Gate)
static constexpr float    INERTIAL_AZ_MIN_G          = 0.85f;
static constexpr float    INERTIAL_AZ_MAX_G          = 1.15f;
static constexpr float    MAX_GYRO_STILL_DPS         = 5.0f;
static constexpr uint32_t BLE_SYNC_WINDOW_MS         = 6000;

} // namespace caphydro
