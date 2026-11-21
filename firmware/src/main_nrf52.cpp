#include <Arduino.h>
#include <Wire.h>
#include <bluefruit.h>
#include <cmath>
#include <cstring>

#include "config.h"
#include "hydration_core.h"
#include "sensor_drivers.h"

using namespace caphydro;

static BLEService        hydrationSvc(SVC_HYDRATION_UUID);
static BLECharacteristic eventChar(CHR_EVENT_UUID);
static BLECharacteristic ackChar(CHR_ACK_UUID);
static BLECharacteristic statusChar(CHR_STATUS_UUID);
static BLEBas            batterySvc;

static LoadCellDriver    loadCell;
static WakeImuDriver     wakeImu;
static HydrationTracker  tracker(DEFAULT_SCALE_COUNTS_PER_G, 0);

static volatile bool     motionWakeFlag = false;
static float             activeCountsPerGram = DEFAULT_SCALE_COUNTS_PER_G;

static void onMotionISR() {
    motionWakeFlag = true;
}

static uint16_t read_vbat_mv() {
    // Enable resistor divider on P0.14 LOW for 1 ms only, then HIGH to eliminate leakage
    pinMode(PIN_VBAT_ENABLE, OUTPUT);
    digitalWrite(PIN_VBAT_ENABLE, LOW);
    delay(1);
    uint32_t raw = analogRead(PIN_VBAT_ADC);
    digitalWrite(PIN_VBAT_ENABLE, HIGH);

    // XIAO nRF52840 ADC: 10-bit default (or 12-bit), 3.6 V ref, 1:3 divider (3x scaling)
    float mv = (static_cast<float>(raw) / 1023.0f) * 3600.0f * 2.961f;
    return static_cast<uint16_t>(constrain(lroundf(mv), 2800L, 4350L));
}

static uint8_t mv_to_percent(uint16_t mv) {
    if (mv >= 4150) return 100;
    if (mv <= 3300) return 0;
    return static_cast<uint8_t>(((mv - 3300) * 100U) / (4150U - 3300U));
}

static void onAckWrite(uint16_t conn_hdl, BLECharacteristic* chr, uint8_t* data, uint16_t len) {
    (void)conn_hdl;
    (void)chr;
    if (len == 4) {
        uint32_t ack_seq = 0;
        std::memcpy(&ack_seq, data, 4);
        tracker.ack_up_to(ack_seq);
    }
}

static void update_status_char() {
    uint16_t vbat_mv = read_vbat_mv();
    float last_g = tracker.last_valid_mass_g();
    DeviceStatus st{
        millis() / 1000UL,
        vbat_mv,
        static_cast<uint16_t>(last_g > 0.0f ? lroundf(last_g) : 0U)
    };
    statusChar.write(&st, sizeof(st));
    batterySvc.write(mv_to_percent(vbat_mv));
}

static void sync_ble_events() {
    update_status_char();
    Bluefruit.Advertising.start(0);
    uint32_t t0 = millis();
    uint32_t sent_offset = 0;

    while (millis() - t0 < BLE_SYNC_WINDOW_MS) {
        if (Bluefruit.connected()) {
            HydrationEvent ev{};
            if (tracker.peek_pending_at(sent_offset, ev)) {
                eventChar.notify(&ev, sizeof(ev));
                ++sent_offset;
                delay(45);
            } else if (tracker.pending_count() == 0) {
                break; // All queued events ACKed by Android Health Connect bridge
            } else {
                sent_offset = 0; // Retry un-ACKed window gently
                delay(150);
            }
        }
        delay(20);
    }
    Bluefruit.Advertising.stop();
}

// Wait briefly until bottle hangs nearly still & vertical before reading strain bridge
static bool wait_for_static_vertical_hold(float& az_out) {
    uint32_t t0 = millis();
    int stable_streak = 0;
    while (millis() - t0 < 2500) {
        float ax = 0.0f, ay = 0.0f, az = 1.0f;
        if (wakeImu.read_accel_g(ax, ay, az)) {
            float horiz = sqrtf(ax * ax + ay * ay);
            if (az >= INERTIAL_AZ_MIN_G && az <= INERTIAL_AZ_MAX_G && horiz < 0.27f) {
                ++stable_streak;
                az_out = az;
                if (stable_streak >= 6) return true; // ~300 ms steady vertical hold
            } else {
                stable_streak = 0;
            }
        }
        delay(50);
    }
    return false;
}

#if ENABLE_USB_DEBUG_CLI
// Active ONLY when a USB-C host is attached (Serial evaluates true); 0 uA impact unplugged
static void service_usb_debug_cli() {
    if (!Serial || !Serial.available()) return;
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "s") {
        Serial.printf("{\"uptime_s\":%lu,\"vbat_mv\":%u,\"last_g\":%.1f,\"zero\":%ld,\"cpg\":%.2f,\"pending\":%lu}\n",
                      millis() / 1000UL, read_vbat_mv(), tracker.last_valid_mass_g(),
                      static_cast<long>(tracker.zero_offset()), activeCountsPerGram,
                      static_cast<unsigned long>(tracker.pending_count()));
    } else if (cmd == "t") {
        int32_t raw[15]{};
        loadCell.read_15_samples(raw);
        tracker.set_calibration(activeCountsPerGram, median_filter_15(raw));
        Serial.printf("OK TARE zero_offset=%ld\n", static_cast<long>(tracker.zero_offset()));
    } else if (cmd.startsWith("c ")) {
        float known_g = cmd.substring(2).toFloat();
        if (known_g >= 50.0f) {
            int32_t raw[15]{};
            loadCell.read_15_samples(raw);
            int32_t delta = median_filter_15(raw) - tracker.zero_offset();
            activeCountsPerGram = static_cast<float>(delta) / known_g;
            tracker.set_calibration(activeCountsPerGram, tracker.zero_offset());
            Serial.printf("OK CAL known_g=%.1f counts_per_g=%.3f\n", known_g, activeCountsPerGram);
        }
    } else if (cmd == "d") {
        HydrationEvent ev{};
        for (uint32_t i = 0; i < tracker.pending_count(); ++i) {
            if (tracker.peek_pending_at(i, ev)) {
                Serial.printf("seq=%lu t=%lus delta_ml=%d mass_g=%u\n",
                              static_cast<unsigned long>(ev.seq), static_cast<unsigned long>(ev.uptime_s),
                              ev.delta_ml, ev.bottle_mass_g);
            }
        }
    } else if (cmd == "b") {
        Serial.println("Rebooting into UF2/DFU USB-C bootloader...");
        Serial.flush();
        enterUf2Dfu();
    } else if (cmd.length() > 0) {
        Serial.println("Cmds: s (status) | t (tare) | c <grams> (calibrate) | d (dump ring) | b (UF2 bootloader)");
    }
}
#endif

void setup() {
#if ENABLE_USB_DEBUG_CLI
    Serial.begin(USB_DEBUG_BAUD);
#endif
    Wire.begin();
    Wire.setClock(400000);

    pinMode(PIN_IMU_INT1, INPUT_PULLDOWN);
    attachInterrupt(digitalPinToInterrupt(PIN_IMU_INT1), onMotionISR, RISING);

    wakeImu.begin();
    loadCell.begin();

    // Initial tare reading at boot (assumes cap rests unweighted on desk)
    int32_t boot_raw[15]{};
    loadCell.read_15_samples(boot_raw);
    tracker.set_calibration(DEFAULT_SCALE_COUNTS_PER_G, median_filter_15(boot_raw));

    Bluefruit.begin();
    Bluefruit.setTxPower(0); // 0 dBm balances ~5 mA TX current & tabletop range
    Bluefruit.setName(BLE_DEVICE_NAME);

    hydrationSvc.begin();

    eventChar.setProperties(CHR_PROPS_NOTIFY | CHR_PROPS_READ);
    eventChar.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
    eventChar.setFixedLen(sizeof(HydrationEvent));
    eventChar.begin();

    ackChar.setProperties(CHR_PROPS_WRITE | CHR_PROPS_WRITE_WO_RESP);
    ackChar.setPermission(SECMODE_NO_ACCESS, SECMODE_OPEN);
    ackChar.setFixedLen(4);
    ackChar.setWriteCallback(onAckWrite);
    ackChar.begin();

    statusChar.setProperties(CHR_PROPS_READ);
    statusChar.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
    statusChar.setFixedLen(sizeof(DeviceStatus));
    statusChar.begin();

    batterySvc.begin();
    update_status_char();

    Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
    Bluefruit.Advertising.addService(hydrationSvc);
    Bluefruit.Advertising.addName();
    Bluefruit.Advertising.restartOnDisconnect(false);
}

void loop() {
#if ENABLE_USB_DEBUG_CLI
    service_usb_debug_cli();
    if (Serial) {
        delay(25);
        return; // Keep USB-C CDC active while plugged into PC for live debugging
    }
#endif
    if (!motionWakeFlag) {
        // Low-power Nordic System-ON idle (~5 uA) until BMA400 INT1 fires
        __WFE();
        __SEV();
        __WFE();
        return;
    }
    motionWakeFlag = false;

    float az_g = 1.0f;
    if (!wait_for_static_vertical_hold(az_g)) {
        return;
    }

    int32_t raw_samples[15]{};
    loadCell.read_15_samples(raw_samples);

    LiftResult res = tracker.process_lift_samples(raw_samples, az_g, millis() / 1000UL, true);
    if (res.should_sync_ble || tracker.pending_count() > 0) {
        sync_ble_events();
    }
}
