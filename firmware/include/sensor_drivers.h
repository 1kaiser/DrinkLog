#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <cstdint>
#include "config.h"

#ifdef SENSOR_NAU7802
#include "SparkFun_Qwiic_Scale_NAU7802_Arduino_Library.h"
#endif

namespace caphydro {

// ===========================================================================
// 1. Load-Sensing Drivers (NAU7802 w/ High-Z AVDD Gate OR TE FX29 I2C Sleep)
// ===========================================================================
#ifdef SENSOR_NAU7802
class LoadCellDriver {
public:
    bool begin() {
        if (!scale_.begin()) return false;
        scale_.setLDO(NAU7802_LDO_2V4);
        scale_.setGain(NAU7802_GAIN_128);
        scale_.setSampleRate(NAU7802_SPS_80);
        scale_.calibrateAFE();
        power_down();
        return true;
    }

    void read_15_samples(int32_t out[15]) {
        scale_.powerUp();             // Enables internal 2.4 V AVDD LDO
        scale_.setLDO(NAU7802_LDO_2V4);
        delay(80);                    // Analog & Wheatstone bridge settle time
        for (int i = 0; i < 15; ++i) {
            uint32_t t0 = millis();
            while (!scale_.available() && (millis() - t0 < 50)) {
                delay(1);
            }
            out[i] = scale_.getReading();
        }
        power_down();
    }

    // Power down analog/digital blocks -> AVDD becomes High-Z (0 uA bridge leak!)
    void power_down() {
        scale_.powerDown();
    }

private:
    NAU7802 scale_;
};
#endif

#ifdef SENSOR_FX29_I2C
class LoadCellDriver {
public:
    bool begin() {
        sleep_sensor();
        return true;
    }

    // TE FX29 I2C Sleep protocol: dummy write wakes ADC, 2-byte read fetches 14-bit count
    void read_15_samples(int32_t out[15]) {
        for (int i = 0; i < 15; ++i) {
            Wire.beginTransmission(I2C_ADDR_FX29);
            Wire.endTransmission();   // Measurement request (wake from 0.5 uA sleep)
            delay(6);
            Wire.requestFrom(I2C_ADDR_FX29, static_cast<uint8_t>(2));
            if (Wire.available() == 2) {
                uint8_t msb = Wire.read();
                uint8_t lsb = Wire.read();
                uint16_t counts = (static_cast<uint16_t>(msb & 0x3F) << 8) | lsb;
                out[i] = static_cast<int32_t>(counts);
            } else {
                out[i] = (i > 0) ? out[i - 1] : 1000;
            }
        }
        sleep_sensor();
    }

    void sleep_sensor() {
        // Sleep-enabled FX29 parts auto-return to 0.5 uA idle between I2C reads
    }
};
#endif

// ===========================================================================
// 2. Wake-on-Motion IMU Drivers (BMA400 @ ~0.9 uA OR LSM6DS3TR-C LP)
// ===========================================================================
inline void i2c_write_reg(uint8_t addr, uint8_t reg, uint8_t val) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    Wire.write(val);
    Wire.endTransmission();
}

inline uint8_t i2c_read_reg(uint8_t addr, uint8_t reg) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    Wire.endTransmission(false);
    Wire.requestFrom(addr, static_cast<uint8_t>(1));
    return Wire.available() ? Wire.read() : 0;
}

#ifdef IMU_BMA400
class WakeImuDriver {
public:
    bool begin() {
        uint8_t chip_id = i2c_read_reg(I2C_ADDR_BMA400, 0x00);
        if (chip_id != 0x90) return false;

        // Low-power 25 Hz mode (~0.9 uA), +/- 4g range
        i2c_write_reg(I2C_ADDR_BMA400, 0x19, 0x01); // ACC_CONFIG0: low power mode
        i2c_write_reg(I2C_ADDR_BMA400, 0x1A, 0x46); // ACC_CONFIG1: +/-4g, 25Hz ODR
        // Generic interrupt 1 (wakeup on motion > ~60 mg across X/Y/Z)
        i2c_write_reg(I2C_ADDR_BMA400, 0x3F, 0xFA); // GEN1INT_CONFIG0: X/Y/Z en, ref update
        i2c_write_reg(I2C_ADDR_BMA400, 0x41, 0x08); // GEN1INT_CONFIG2: threshold ~64 mg
        i2c_write_reg(I2C_ADDR_BMA400, 0x1F, 0x04); // INT_CONFIG0: gen1_int_en
        i2c_write_reg(I2C_ADDR_BMA400, 0x21, 0x04); // INT1_MAP: map gen1 to INT1
        i2c_write_reg(I2C_ADDR_BMA400, 0x24, 0x02); // INT12_IO_CTRL: push-pull active HIGH
        return true;
    }

    bool read_accel_g(float& ax, float& ay, float& az) {
        Wire.beginTransmission(I2C_ADDR_BMA400);
        Wire.write(0x04); // ACC_X_LSB
        Wire.endTransmission(false);
        if (Wire.requestFrom(I2C_ADDR_BMA400, static_cast<uint8_t>(6)) != 6) return false;

        auto decode12 = [](uint8_t lsb, uint8_t msb) -> float {
            int16_t v = static_cast<int16_t>((static_cast<uint16_t>(msb & 0x0F) << 8) | lsb);
            if (v > 2047) v -= 4096;
            return static_cast<float>(v) * (4.0f / 2048.0f); // +/- 4g scale
        };
        uint8_t buf[6];
        for (int i = 0; i < 6; ++i) buf[i] = Wire.read();
        ax = decode12(buf[0], buf[1]);
        ay = decode12(buf[2], buf[3]);
        az = decode12(buf[4], buf[5]);
        return true;
    }
};
#endif

#ifdef IMU_LSM6DS3_SENSE
class WakeImuDriver {
public:
    bool begin() {
        uint8_t who = i2c_read_reg(I2C_ADDR_LSM6DS3, 0x0F);
        if (who != 0x69 && who != 0x6A) return false;

        // CRITICAL: Shut down gyroscope completely (0x00) to avoid ~200 uA standby trap!
        i2c_write_reg(I2C_ADDR_LSM6DS3, 0x11, 0x00); // CTRL2_G = Power-down
        i2c_write_reg(I2C_ADDR_LSM6DS3, 0x15, 0x10); // CTRL6_C = XL_HM_MODE=1 (Low Power)
        i2c_write_reg(I2C_ADDR_LSM6DS3, 0x10, 0x18); // CTRL1_XL = 12.5 Hz, +/- 4g
        i2c_write_reg(I2C_ADDR_LSM6DS3, 0x58, 0x80); // TAP_CFG = LIR / interrupt enable
        i2c_write_reg(I2C_ADDR_LSM6DS3, 0x5B, 0x02); // WAKE_UP_THS
        i2c_write_reg(I2C_ADDR_LSM6DS3, 0x5E, 0x20); // MD1_CFG = INT1_WU
        return true;
    }

    bool read_accel_g(float& ax, float& ay, float& az) {
        Wire.beginTransmission(I2C_ADDR_LSM6DS3);
        Wire.write(0x28); // OUTX_L_XL
        Wire.endTransmission(false);
        if (Wire.requestFrom(I2C_ADDR_LSM6DS3, static_cast<uint8_t>(6)) != 6) return false;
        uint8_t buf[6];
        for (int i = 0; i < 6; ++i) buf[i] = Wire.read();
        auto dec = [](uint8_t l, uint8_t h) -> float {
            int16_t v = static_cast<int16_t>((static_cast<uint16_t>(h) << 8) | l);
            return static_cast<float>(v) * 0.000122f; // +/- 4g sensitivity (0.122 mg/LSB)
        };
        ax = dec(buf[0], buf[1]);
        ay = dec(buf[2], buf[3]);
        az = dec(buf[4], buf[5]);
        return true;
    }
};
#endif

} // namespace caphydro
