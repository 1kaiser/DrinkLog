#include <Arduino.h>
#include <NimBLEDevice.h>
#include <Wire.h>
#include <cmath>
#include <cstring>
#include "esp_sleep.h"

#include "config.h"
#include "hydration_core.h"
#include "sensor_drivers.h"

using namespace caphydro;

// Persist tracker state & 64-event ring buffer across ESP32-C6 deep sleep (~15-20 uA)
RTC_DATA_ATTR static HydrationTracker rtc_tracker(DEFAULT_SCALE_COUNTS_PER_G, 0);
RTC_DATA_ATTR static bool             rtc_initialized = false;
RTC_DATA_ATTR static uint32_t         rtc_cumulative_uptime_s = 0;

static LoadCellDriver loadCell;
static WakeImuDriver  wakeImu;

class AckCallbacks : public NimBLECharacteristicCallbacks {
    void onWrite(NimBLECharacteristic* pChar) override {
        std::string val = pChar->getValue();
        if (val.size() == 4) {
            uint32_t seq = 0;
            std::memcpy(&seq, val.data(), 4);
            rtc_tracker.ack_up_to(seq);
        }
    }
};
static AckCallbacks ackCallbacks;

static uint16_t read_vbat_mv() {
    uint32_t mv = analogReadMilliVolts(PIN_VBAT_ADC) * 2U; // Assumes 1:2 divider
    return static_cast<uint16_t>(constrain(mv, 2800UL, 4350UL));
}

static bool wait_for_static_vertical_hold(float& az_out) {
    uint32_t t0 = millis();
    int streak = 0;
    while (millis() - t0 < 2500) {
        float ax = 0.0f, ay = 0.0f, az = 1.0f;
        if (wakeImu.read_accel_g(ax, ay, az)) {
            float horiz = sqrtf(ax * ax + ay * ay);
            if (az >= INERTIAL_AZ_MIN_G && az <= INERTIAL_AZ_MAX_G && horiz < 0.27f) {
                ++streak;
                az_out = az;
                if (streak >= 6) return true;
            } else {
                streak = 0;
            }
        }
        delay(50);
    }
    return false;
}

static void sync_ble_events() {
    // Keep Wi-Fi permanently OFF; start NimBLE only for brief sync window
    NimBLEDevice::init(BLE_DEVICE_NAME);
    NimBLEDevice::setPower(ESP_PWR_LVL_N0);

    NimBLEServer* pServer = NimBLEDevice::createServer();
    NimBLEService* pSvc = pServer->createService(SVC_HYDRATION_UUID);

    NimBLECharacteristic* pEvent = pSvc->createCharacteristic(
        CHR_EVENT_UUID, NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY);
    NimBLECharacteristic* pAck = pSvc->createCharacteristic(
        CHR_ACK_UUID, NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR);
    pAck->setCallbacks(&ackCallbacks);
    NimBLECharacteristic* pStatus = pSvc->createCharacteristic(
        CHR_STATUS_UUID, NIMBLE_PROPERTY::READ);

    uint32_t now_s = rtc_cumulative_uptime_s + (millis() / 1000UL);
    float last_g = rtc_tracker.last_valid_mass_g();
    DeviceStatus st{
        now_s,
        read_vbat_mv(),
        static_cast<uint16_t>(last_g > 0.0f ? lroundf(last_g) : 0U)
    };
    pStatus->setValue(reinterpret_cast<uint8_t*>(&st), sizeof(st));
    pSvc->start();

    NimBLEAdvertising* pAdv = NimBLEDevice::getAdvertising();
    pAdv->addServiceUUID(SVC_HYDRATION_UUID);
    pAdv->start();

    uint32_t t0 = millis();
    uint32_t sent_offset = 0;
    while (millis() - t0 < BLE_SYNC_WINDOW_MS) {
        if (pServer->getConnectedCount() > 0) {
            HydrationEvent ev{};
            if (rtc_tracker.peek_pending_at(sent_offset, ev)) {
                pEvent->setValue(reinterpret_cast<uint8_t*>(&ev), sizeof(ev));
                pEvent->notify();
                ++sent_offset;
                delay(45);
            } else if (rtc_tracker.pending_count() == 0) {
                break;
            } else {
                sent_offset = 0;
                delay(150);
            }
        }
        delay(20);
    }

    NimBLEDevice::deinit(true);
}

void setup() {
    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, 400000);
    pinMode(PIN_IMU_INT1, INPUT_PULLDOWN);

    wakeImu.begin();
    loadCell.begin();

    if (!rtc_initialized) {
        int32_t boot_raw[15]{};
        loadCell.read_15_samples(boot_raw);
        rtc_tracker.set_calibration(DEFAULT_SCALE_COUNTS_PER_G, median_filter_15(boot_raw));
        rtc_initialized = true;
    } else {
        float az_g = 1.0f;
        if (wait_for_static_vertical_hold(az_g)) {
            int32_t raw[15]{};
            loadCell.read_15_samples(raw);
            uint32_t now_s = rtc_cumulative_uptime_s + (millis() / 1000UL);
            LiftResult res = rtc_tracker.process_lift_samples(raw, az_g, now_s, true);
            if (res.should_sync_ble || rtc_tracker.pending_count() > 0) {
                sync_ble_events();
            }
        }
    }

    rtc_cumulative_uptime_s += (millis() / 1000UL) + 1UL;
    esp_deep_sleep_enable_gpio_wakeup(1ULL << PIN_IMU_INT1, ESP_GPIO_WAKEUP_GPIO_HIGH);
    esp_deep_sleep_start();
}

void loop() {
    // Never reached; ESP32-C6 always enters deep sleep at end of setup()
}
