#pragma once
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include "config.h"

namespace caphydro {

// ---------------------------------------------------------------------------
// Wire-Format BLE GATT Structs (Little-Endian, Packed)
// ---------------------------------------------------------------------------
struct __attribute__((packed)) HydrationEvent {
    uint32_t seq;           // Monotonic event sequence starting at 1
    uint32_t uptime_s;      // Device seconds since boot
    int16_t  delta_ml;      // >0 = consumed mL, 0 = baseline/refill snapshot
    uint16_t bottle_mass_g; // Stabilized bottle mass after event (grams)
};
static_assert(sizeof(HydrationEvent) == 12, "HydrationEvent must be 12 bytes");

struct __attribute__((packed)) DeviceStatus {
    uint32_t device_uptime_s; // Current device uptime for timestamp sync
    uint16_t vbat_mv;         // Battery voltage in mV
    uint16_t last_mass_g;     // Most recent stable bottle mass in grams
};
static_assert(sizeof(DeviceStatus) == 8, "DeviceStatus must be 8 bytes");

enum class LiftOutcome : uint8_t {
    UnloadedAutoTare = 0, // Cap unscrewed (< MIN_BOTTLE_MASS_G); zero offset updated
    BaselineInit     = 1, // First valid bottle lift recorded
    SipLogged        = 2, // Negative mass delta >= SIP_THRESHOLD_G logged
    RefillDetected   = 3, // Positive mass jump >= |REFILL_THRESHOLD_G| logged
    IgnoredJitter    = 4, // Small noise (< SIP_THRESHOLD_G) or out-of-range
    InvalidInertial  = 5  // Bottle accelerating/tilted outside static vertical gate
};

struct LiftResult {
    LiftOutcome outcome;
    float       measured_mass_g;
    int16_t     delta_ml;
    bool        should_sync_ble;
};

// ---------------------------------------------------------------------------
// 15-Sample Median Filter (Rejects Hand-Jerk Outliers Without Floating Error)
// ---------------------------------------------------------------------------
inline int32_t median_filter_15(const int32_t raw[15]) {
    int32_t buf[15];
    for (int i = 0; i < 15; ++i) {
        buf[i] = raw[i];
    }
    for (int i = 1; i < 15; ++i) {
        const int32_t key = buf[i];
        int j = i - 1;
        while (j >= 0 && buf[j] > key) {
            buf[j + 1] = buf[j];
            --j;
        }
        buf[j + 1] = key;
    }
    return buf[7];
}

inline float clamp_f(float v, float lo, float hi) {
    return (v < lo) ? lo : ((v > hi) ? hi : v);
}

// ---------------------------------------------------------------------------
// Core Hydration State Machine & 64-Event Non-Volatile Ring Buffer
// ---------------------------------------------------------------------------
class HydrationTracker {
public:
    static constexpr size_t RING_CAPACITY = 64;

    explicit HydrationTracker(float counts_per_gram = DEFAULT_SCALE_COUNTS_PER_G,
                              int32_t initial_zero_offset = 0)
        : counts_per_g_(counts_per_gram),
          zero_offset_(initial_zero_offset) {}

    void set_calibration(float counts_per_gram, int32_t zero_offset) {
        counts_per_g_ = (counts_per_gram > 1e-3f) ? counts_per_gram : 1.0f;
        zero_offset_ = zero_offset;
    }

    int32_t zero_offset() const { return zero_offset_; }
    float last_valid_mass_g() const { return last_valid_mass_g_; }
    uint32_t head_seq() const { return head_seq_; }
    uint32_t acked_seq() const { return acked_seq_; }

    uint32_t pending_count() const {
        if (head_seq_ <= acked_seq_) return 0;
        uint32_t diff = head_seq_ - acked_seq_;
        return (diff > RING_CAPACITY) ? static_cast<uint32_t>(RING_CAPACITY) : diff;
    }

    // Processes one lift measurement (15 raw ADC counts + IMU vertical az in g).
    LiftResult process_lift_samples(const int32_t raw_samples[15],
                                    float az_g,
                                    uint32_t uptime_s,
                                    bool check_inertial_gate = true) {
        if (check_inertial_gate && (az_g < INERTIAL_AZ_MIN_G || az_g > INERTIAL_AZ_MAX_G)) {
            return {LiftOutcome::InvalidInertial, 0.0f, 0, false};
        }

        const int32_t median_raw = median_filter_15(raw_samples);
        const float raw_g = static_cast<float>(median_raw - zero_offset_) / counts_per_g_;

        // Unloaded cap (unscrewed): smoothly update zero offset via EMA (auto-tare)
        if (std::fabs(raw_g) < MIN_BOTTLE_MASS_G) {
            zero_offset_ = static_cast<int32_t>(
                std::lround((1.0f - AUTO_TARE_EMA_ALPHA) * static_cast<float>(zero_offset_) +
                            AUTO_TARE_EMA_ALPHA * static_cast<float>(median_raw))
            );
            return {LiftOutcome::UnloadedAutoTare, 0.0f, 0, false};
        }

        // Inertial & slight-tilt correction: m = F_z / a_z
        const float clamped_az = clamp_f(az_g, INERTIAL_AZ_MIN_G, INERTIAL_AZ_MAX_G);
        const float mass_g = raw_g / clamped_az;

        if (mass_g < MIN_BOTTLE_MASS_G || mass_g > MAX_VALID_BOTTLE_G) {
            return {LiftOutcome::IgnoredJitter, mass_g, 0, false};
        }

        const uint16_t mass_rounded = static_cast<uint16_t>(std::lround(mass_g));

        // First recorded lift initializes baseline without logging artificial intake
        if (last_valid_mass_g_ < 0.0f) {
            last_valid_mass_g_ = mass_g;
            push_event(uptime_s, 0, mass_rounded);
            return {LiftOutcome::BaselineInit, mass_g, 0, true};
        }

        const float delta_g = last_valid_mass_g_ - mass_g;

        if (delta_g >= SIP_THRESHOLD_G) {
            const int16_t consumed_ml = static_cast<int16_t>(
                std::lround(delta_g / WATER_DENSITY_G_PER_ML)
            );
            last_valid_mass_g_ = mass_g;
            push_event(uptime_s, consumed_ml, mass_rounded);
            return {LiftOutcome::SipLogged, mass_g, consumed_ml, true};
        }

        if (delta_g <= REFILL_THRESHOLD_G) {
            last_valid_mass_g_ = mass_g;
            push_event(uptime_s, 0, mass_rounded);
            return {LiftOutcome::RefillDetected, mass_g, 0, true};
        }

        return {LiftOutcome::IgnoredJitter, mass_g, 0, false};
    }

    // Retrieves oldest unacknowledged event without removing it until ACK arrives.
    bool peek_oldest_unacked(HydrationEvent& out) const {
        if (acked_seq_ >= head_seq_) return false;
        uint32_t oldest_seq = acked_seq_ + 1;
        if (head_seq_ - acked_seq_ > RING_CAPACITY) {
            oldest_seq = head_seq_ - static_cast<uint32_t>(RING_CAPACITY) + 1;
        }
        out = ring_buf_[oldest_seq % RING_CAPACITY];
        return (out.seq == oldest_seq);
    }

    // Returns event by index offset [0, pending_count()-1] from oldest unacked.
    bool peek_pending_at(uint32_t offset, HydrationEvent& out) const {
        const uint32_t pending = pending_count();
        if (offset >= pending) return false;
        uint32_t oldest_seq = (head_seq_ - acked_seq_ > RING_CAPACITY)
                                  ? (head_seq_ - static_cast<uint32_t>(RING_CAPACITY) + 1)
                                  : (acked_seq_ + 1);
        const uint32_t target_seq = oldest_seq + offset;
        out = ring_buf_[target_seq % RING_CAPACITY];
        return (out.seq == target_seq);
    }

    bool ack_up_to(uint32_t seq) {
        if (seq > acked_seq_ && seq <= head_seq_) {
            acked_seq_ = seq;
            return true;
        }
        return false;
    }

private:
    void push_event(uint32_t uptime_s, int16_t delta_ml, uint16_t mass_g) {
        ++head_seq_;
        ring_buf_[head_seq_ % RING_CAPACITY] = HydrationEvent{
            head_seq_,
            uptime_s,
            delta_ml,
            mass_g
        };
    }

    float          counts_per_g_;
    int32_t        zero_offset_;
    float          last_valid_mass_g_ = -1.0f;
    uint32_t       head_seq_          = 0;
    uint32_t       acked_seq_         = 0;
    HydrationEvent ring_buf_[RING_CAPACITY]{};
};

} // namespace caphydro
