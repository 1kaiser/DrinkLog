#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include "hydration_core.h"

using namespace drinklog;

static void fill_samples(int32_t out[15], int32_t center, int32_t noise_step = 2) {
    for (int i = 0; i < 15; ++i) {
        out[i] = center + ((i % 3) - 1) * noise_step;
    }
}

int main() {
    // 1. Exact binary wire sizes & field offsets (matches Python/Kotlin decoders)
    static_assert(sizeof(HydrationEvent) == 12, "HydrationEvent size mismatch");
    static_assert(sizeof(DeviceStatus) == 8, "DeviceStatus size mismatch");
    assert(offsetof(HydrationEvent, seq) == 0);
    assert(offsetof(HydrationEvent, uptime_s) == 4);
    assert(offsetof(HydrationEvent, delta_ml) == 8);
    assert(offsetof(HydrationEvent, bottle_mass_g) == 10);

    // 2. Median filter rejects severe single/triple hand-jerk outliers
    int32_t noisy[15] = {
        420500, 420510, 9999999, 420495, -500000,
        420505, 420490, 420500, 900000, 420502,
        420498, 420501, 420499, -999999, 420503
    };
    int32_t med = median_filter_15(noisy);
    assert(med >= 420498 && med <= 420503);

    // 3. Calibration & auto-tare drift tracking when cap is unscrewed
    const float CPG = 400.0f;
    const int32_t ZERO = 100000;
    HydrationTracker tracker(CPG, ZERO);

    int32_t raw[15]{};
    // Cap unscrewed with +10 g thermal offset drift -> should auto-tare toward 104000
    fill_samples(raw, ZERO + 4000);
    LiftResult tare_res = tracker.process_lift_samples(raw, 1.0f, 10);
    assert(tare_res.outcome == LiftOutcome::UnloadedAutoTare);
    assert(tracker.zero_offset() == 100800); // 0.8*100000 + 0.2*104000
    assert(tracker.pending_count() == 0);

    // Reset clean zero for deterministic drinking test
    tracker.set_calibration(CPG, ZERO);

    // 4. Inertial compensation check: 1000 g bottle accelerating upward at 1.10g reads 1100 g force
    fill_samples(raw, ZERO + static_cast<int32_t>(1100.0f * CPG));
    LiftResult init_res = tracker.process_lift_samples(raw, 1.10f, 100);
    assert(init_res.outcome == LiftOutcome::BaselineInit);
    assert(std::fabs(init_res.measured_mass_g - 1000.0f) < 1.0f);
    assert(init_res.delta_ml == 0);
    assert(tracker.pending_count() == 1);

    // Out-of-bounds violent shake (1.35g) must be rejected cleanly
    LiftResult shake_res = tracker.process_lift_samples(raw, 1.35f, 105);
    assert(shake_res.outcome == LiftOutcome::InvalidInertial);
    assert(tracker.pending_count() == 1);

    // 5. Realistic drinking sequence:
    // Sip 1: 1000 g -> 790 g (210 mL consumed)
    fill_samples(raw, ZERO + static_cast<int32_t>(790.0f * CPG));
    LiftResult sip1 = tracker.process_lift_samples(raw, 1.00f, 300);
    assert(sip1.outcome == LiftOutcome::SipLogged);
    assert(sip1.delta_ml == 210);
    assert(tracker.pending_count() == 2);

    // Small vibration/slosh (< 15 g): 790 g -> 785 g -> ignored
    fill_samples(raw, ZERO + static_cast<int32_t>(785.0f * CPG));
    LiftResult noise = tracker.process_lift_samples(raw, 1.00f, 320);
    assert(noise.outcome == LiftOutcome::IgnoredJitter);
    assert(tracker.pending_count() == 2);

    // Sip 2: 790 g -> 605 g (185 mL consumed)
    fill_samples(raw, ZERO + static_cast<int32_t>(605.0f * CPG));
    LiftResult sip2 = tracker.process_lift_samples(raw, 1.00f, 600);
    assert(sip2.outcome == LiftOutcome::SipLogged);
    assert(sip2.delta_ml == 185);
    assert(tracker.pending_count() == 3);

    // Refill: 605 g -> 1105 g (+500 g added) -> logs snapshot delta_ml=0, updates baseline
    fill_samples(raw, ZERO + static_cast<int32_t>(1105.0f * CPG));
    LiftResult refill = tracker.process_lift_samples(raw, 1.00f, 900);
    assert(refill.outcome == LiftOutcome::RefillDetected);
    assert(refill.delta_ml == 0);
    assert(std::fabs(tracker.last_valid_mass_g() - 1105.0f) < 1.0f);

    // Sip 3 after refill: 1105 g -> 985 g (120 mL consumed)
    fill_samples(raw, ZERO + static_cast<int32_t>(985.0f * CPG));
    LiftResult sip3 = tracker.process_lift_samples(raw, 1.00f, 1200);
    assert(sip3.outcome == LiftOutcome::SipLogged);
    assert(sip3.delta_ml == 120);
    assert(tracker.pending_count() == 5); // baseline + sip1 + sip2 + refill + sip3

    // Verify FIFO peek + partial ACK
    HydrationEvent ev{};
    assert(tracker.peek_oldest_unacked(ev));
    assert(ev.seq == 1 && ev.delta_ml == 0 && ev.bottle_mass_g == 1000);
    assert(tracker.ack_up_to(2)); // ACK baseline + sip1
    assert(tracker.pending_count() == 3);
    assert(tracker.peek_oldest_unacked(ev));
    assert(ev.seq == 3 && ev.delta_ml == 185);

    // 6. Ring buffer overflow (> 64 offline events) preserves latest 64 events cleanly
    float m = 985.0f;
    for (int k = 0; k < 80; ++k) {
        m -= 20.0f;
        if (m < 100.0f) m = 1100.0f; // virtual refill
        fill_samples(raw, ZERO + static_cast<int32_t>(m * CPG));
        tracker.process_lift_samples(raw, 1.0f, 2000 + static_cast<uint32_t>(k * 60));
    }
    assert(tracker.pending_count() == HydrationTracker::RING_CAPACITY);
    assert(tracker.peek_oldest_unacked(ev));
    assert(ev.seq == tracker.head_seq() - HydrationTracker::RING_CAPACITY + 1);
    assert(tracker.ack_up_to(tracker.head_seq()));
    assert(tracker.pending_count() == 0);

    std::cout << "[PASS] All DrinkLog C++17 firmware core unit tests passed (6/6 groups).\n";
    return 0;
}
