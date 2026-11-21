package com.drinklog.app

import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.records.HydrationRecord
import androidx.health.connect.client.records.metadata.Device
import androidx.health.connect.client.records.metadata.Metadata
import androidx.health.connect.client.units.Volume
import java.time.Instant
import java.time.ZoneOffset

/**
 * Inserts DrinkLog sip events into Android Health Connect with deterministic
 * clientRecordId deduplication so retried BLE syncs never double-log fluid intake.
 */
class HealthConnectSyncManager(
    private val client: HealthConnectClient
) {
    suspend fun recordSip(
        deviceMac: String,
        event: HydrationEventPacket,
        deviceUptimeS: Long,
        syncNow: Instant = Instant.now(),
        estimatedSipDurationSeconds: Long = 10L
    ): Boolean {
        // Baseline/refill snapshots carry deltaMl == 0; nothing consumed
        if (event.deltaMl <= 0) return true

        val sipEnd = BleGattProtocol.reconstructEventInstant(syncNow, deviceUptimeS, event.uptimeS)
        val sipStart = sipEnd.minusSeconds(estimatedSipDurationSeconds)
        val zoneOffset = ZoneOffset.systemDefault().rules.getOffset(sipEnd)

        val record = HydrationRecord(
            startTime = sipStart,
            startZoneOffset = zoneOffset,
            endTime = sipEnd,
            endZoneOffset = zoneOffset,
            volume = Volume.milliliters(event.deltaMl.toDouble()),
            metadata = Metadata.autoRecorded(
                device = Device(type = Device.TYPE_UNKNOWN),
                clientRecordId = "drinklog-${deviceMac.replace(":", "")}-${event.seq}"
            )
        )
        client.insertRecords(listOf(record))
        return true
    }
}
