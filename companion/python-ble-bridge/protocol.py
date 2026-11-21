"""
Binary BLE GATT protocol codec (1:1 parity with firmware/include/hydration_core.h
and Android BleGattProtocol.kt) plus a 24-hour bottle hydration event simulator.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List

SVC_HYDRATION_UUID = "7a4b0001-3c9e-4f1a-9b2d-8e5c10293847"
CHR_EVENT_UUID     = "7a4b0002-3c9e-4f1a-9b2d-8e5c10293847"
CHR_ACK_UUID       = "7a4b0003-3c9e-4f1a-9b2d-8e5c10293847"
CHR_STATUS_UUID    = "7a4b0004-3c9e-4f1a-9b2d-8e5c10293847"

EVENT_STRUCT  = struct.Struct("<IIhH")  # seq, uptime_s, delta_ml, bottle_mass_g (12 B)
STATUS_STRUCT = struct.Struct("<IHH")   # device_uptime_s, vbat_mv, last_mass_g (8 B)
ACK_STRUCT    = struct.Struct("<I")     # last_acked_seq (4 B)


@dataclass(frozen=True)
class HydrationEvent:
    seq: int
    uptime_s: int
    delta_ml: int
    bottle_mass_g: int

    def encode(self) -> bytes:
        return EVENT_STRUCT.pack(self.seq, self.uptime_s, self.delta_ml, self.bottle_mass_g)

    @classmethod
    def decode(cls, payload: bytes) -> "HydrationEvent":
        if len(payload) != EVENT_STRUCT.size:
            raise ValueError(f"Expected {EVENT_STRUCT.size} bytes, got {len(payload)}")
        seq, uptime_s, delta_ml, mass_g = EVENT_STRUCT.unpack(payload)
        return cls(seq=seq, uptime_s=uptime_s, delta_ml=delta_ml, bottle_mass_g=mass_g)


@dataclass(frozen=True)
class DeviceStatus:
    device_uptime_s: int
    vbat_mv: int
    last_mass_g: int

    def encode(self) -> bytes:
        return STATUS_STRUCT.pack(self.device_uptime_s, self.vbat_mv, self.last_mass_g)

    @classmethod
    def decode(cls, payload: bytes) -> "DeviceStatus":
        if len(payload) != STATUS_STRUCT.size:
            raise ValueError(f"Expected {STATUS_STRUCT.size} bytes, got {len(payload)}")
        uptime_s, vbat_mv, last_mass_g = STATUS_STRUCT.unpack(payload)
        return cls(device_uptime_s=uptime_s, vbat_mv=vbat_mv, last_mass_g=last_mass_g)


def encode_ack(seq: int) -> bytes:
    return ACK_STRUCT.pack(seq)


def decode_ack(payload: bytes) -> int:
    if len(payload) != ACK_STRUCT.size:
        raise ValueError(f"Expected {ACK_STRUCT.size} bytes, got {len(payload)}")
    return ACK_STRUCT.unpack(payload)[0]


def reconstruct_timestamp(sync_now: datetime, device_uptime_s: int, event_uptime_s: int) -> datetime:
    age_s = max(0, device_uptime_s - event_uptime_s)
    return sync_now - timedelta(seconds=age_s)


def simulate_24h_bottle_day(
    sip_thresh_g: float = 15.0,
    refill_thresh_g: float = -25.0,
) -> List[HydrationEvent]:
    """
    Simulate realistic 24-hour lifts: initial fill, 9 sips, mid-day refill,
    unscrew auto-tare checks (<45 g ignored by event queue), and noise (<15 g).
    """
    # (hour_of_day, mass_g)
    observations = [
        (7.0, 1180.0),   # Morning baseline (750 mL water + 430 g bottle)
        (7.5, 970.0),    # Sip 1: 210 mL
        (8.8, 963.0),    # Table bump / jitter (<15 g -> ignored)
        (9.2, 745.0),    # Sip 2: 225 mL
        (10.5, 560.0),   # Sip 3: 185 mL
        (12.1, 410.0),   # Sip 4: 150 mL
        (13.0, 1175.0),  # Refill (+765 g -> delta_ml = 0, update baseline)
        (14.3, 945.0),   # Sip 5: 230 mL
        (15.8, 725.0),   # Sip 6: 220 mL
        (17.4, 515.0),   # Sip 7: 210 mL
        (19.0, 1160.0),  # Evening refill (+645 g)
        (19.8, 930.0),   # Sip 8: 230 mL
        (21.5, 760.0),   # Sip 9: 170 mL
    ]

    events: List[HydrationEvent] = []
    last_mass: float | None = None
    seq = 0

    for hour, mass in observations:
        uptime_s = int(round(hour * 3600))
        if last_mass is None:
            seq += 1
            last_mass = mass
            events.append(HydrationEvent(seq=seq, uptime_s=uptime_s, delta_ml=0, bottle_mass_g=int(round(mass))))
            continue

        delta_g = last_mass - mass
        if delta_g >= sip_thresh_g:
            seq += 1
            last_mass = mass
            events.append(
                HydrationEvent(
                    seq=seq,
                    uptime_s=uptime_s,
                    delta_ml=int(round(delta_g)),
                    bottle_mass_g=int(round(mass)),
                )
            )
        elif delta_g <= refill_thresh_g:
            seq += 1
            last_mass = mass
            events.append(
                HydrationEvent(
                    seq=seq,
                    uptime_s=uptime_s,
                    delta_ml=0,
                    bottle_mass_g=int(round(mass)),
                )
            )

    return events
