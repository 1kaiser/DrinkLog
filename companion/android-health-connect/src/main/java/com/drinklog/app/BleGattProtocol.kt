package com.drinklog.app

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.time.Instant
import java.util.UUID

object BleGattUuids {
    val SERVICE_HYDRATION: UUID = UUID.fromString("7a4b0001-3c9e-4f1a-9b2d-8e5c10293847")
    val CHAR_EVENT: UUID        = UUID.fromString("7a4b0002-3c9e-4f1a-9b2d-8e5c10293847")
    val CHAR_ACK: UUID          = UUID.fromString("7a4b0003-3c9e-4f1a-9b2d-8e5c10293847")
    val CHAR_STATUS: UUID       = UUID.fromString("7a4b0004-3c9e-4f1a-9b2d-8e5c10293847")
    val CCCD_DESCRIPTOR: UUID   = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
}

data class HydrationEventPacket(
    val seq: Long,          // uint32
    val uptimeS: Long,      // uint32
    val deltaMl: Int,       // int16 (>0 = consumed fluid mL, 0 = baseline/refill)
    val bottleMassG: Int    // uint16
)

data class DeviceStatusPacket(
    val deviceUptimeS: Long, // uint32
    val vbatMv: Int,         // uint16
    val lastMassG: Int       // uint16
)

object BleGattProtocol {

    fun decodeEvent(bytes: ByteArray): HydrationEventPacket {
        require(bytes.size == 12) { "Expected 12-byte HydrationEvent, got ${bytes.size}" }
        val buf = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        val seq = buf.int.toLong() and 0xFFFFFFFFL
        val uptimeS = buf.int.toLong() and 0xFFFFFFFFL
        val deltaMl = buf.short.toInt()
        val bottleMassG = buf.short.toInt() and 0xFFFF
        return HydrationEventPacket(seq, uptimeS, deltaMl, bottleMassG)
    }

    fun decodeStatus(bytes: ByteArray): DeviceStatusPacket {
        require(bytes.size == 8) { "Expected 8-byte DeviceStatus, got ${bytes.size}" }
        val buf = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        val uptimeS = buf.int.toLong() and 0xFFFFFFFFL
        val vbatMv = buf.short.toInt() and 0xFFFF
        val lastMassG = buf.short.toInt() and 0xFFFF
        return DeviceStatusPacket(uptimeS, vbatMv, lastMassG)
    }

    fun encodeAck(seq: Long): ByteArray {
        return ByteBuffer.allocate(4)
            .order(ByteOrder.LITTLE_ENDIAN)
            .putInt((seq and 0xFFFFFFFFL).toInt())
            .array()
    }

    /** Reconstruct wall-clock timestamp even for events buffered offline. */
    fun reconstructEventInstant(now: Instant, deviceUptimeS: Long, eventUptimeS: Long): Instant {
        val ageSeconds = (deviceUptimeS - eventUptimeS).coerceAtLeast(0L)
        return now.minusSeconds(ageSeconds)
    }
}
