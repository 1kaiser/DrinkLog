package com.caphydro.app

import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothProfile
import android.content.Context
import android.os.Build
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * Connects to CapHydro over BLE, reads DeviceStatus (0004) for offline clock
 * reconstruction, subscribes to Event (0002), inserts HydrationRecord into Health
 * Connect, and writes ACK (0003) ONLY after Health Connect confirms persistence.
 */
@SuppressLint("MissingPermission")
class CapHydroBleClient(
    private val context: Context,
    private val syncManager: HealthConnectSyncManager,
    private val scope: CoroutineScope
) {
    private var activeGatt: BluetoothGatt? = null
    @Volatile
    private var latestDeviceUptimeS: Long = 0L

    fun connect(device: BluetoothDevice) {
        activeGatt = device.connectGatt(context, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
    }

    fun disconnect() {
        activeGatt?.disconnect()
        activeGatt?.close()
        activeGatt = null
    }

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                gatt.discoverServices()
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                gatt.close()
            }
        }

        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) return
            val svc = gatt.getService(BleGattUuids.SERVICE_HYDRATION) ?: return
            val statusChar = svc.getCharacteristic(BleGattUuids.CHAR_STATUS) ?: return
            gatt.readCharacteristic(statusChar)
        }

        @Deprecated("Deprecated in API 33")
        override fun onCharacteristicRead(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            status: Int
        ) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                @Suppress("DEPRECATION")
                handleStatusAndEnableNotify(gatt, characteristic.value)
            }
        }

        override fun onCharacteristicRead(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            value: ByteArray,
            status: Int
        ) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                handleStatusAndEnableNotify(gatt, value)
            }
        }

        @Deprecated("Deprecated in API 33")
        override fun onCharacteristicChanged(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic
        ) {
            @Suppress("DEPRECATION")
            handleEventNotification(gatt, characteristic.value)
        }

        override fun onCharacteristicChanged(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            value: ByteArray
        ) {
            handleEventNotification(gatt, value)
        }
    }

    private fun handleStatusAndEnableNotify(gatt: BluetoothGatt, statusBytes: ByteArray) {
        if (statusBytes.size == 8) {
            latestDeviceUptimeS = BleGattProtocol.decodeStatus(statusBytes).deviceUptimeS
        }
        val svc = gatt.getService(BleGattUuids.SERVICE_HYDRATION) ?: return
        val eventChar = svc.getCharacteristic(BleGattUuids.CHAR_EVENT) ?: return
        gatt.setCharacteristicNotification(eventChar, true)
        val cccd = eventChar.getDescriptor(BleGattUuids.CCCD_DESCRIPTOR) ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            gatt.writeDescriptor(cccd, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
        } else {
            @Suppress("DEPRECATION")
            cccd.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
            @Suppress("DEPRECATION")
            gatt.writeDescriptor(cccd)
        }
    }

    private fun handleEventNotification(gatt: BluetoothGatt, payload: ByteArray) {
        if (payload.size != 12) return
        val ev = BleGattProtocol.decodeEvent(payload)
        val mac = gatt.device.address ?: "000000000000"

        scope.launch(Dispatchers.IO) {
            val saved = syncManager.recordSip(
                deviceMac = mac,
                event = ev,
                deviceUptimeS = maxOf(latestDeviceUptimeS, ev.uptimeS)
            )
            if (saved) {
                val ackChar = gatt.getService(BleGattUuids.SERVICE_HYDRATION)
                    ?.getCharacteristic(BleGattUuids.CHAR_ACK) ?: return@launch
                val ackBytes = BleGattProtocol.encodeAck(ev.seq)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    gatt.writeCharacteristic(
                        ackChar, ackBytes, BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
                    )
                } else {
                    @Suppress("DEPRECATION")
                    ackChar.value = ackBytes
                    @Suppress("DEPRECATION")
                    ackChar.writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
                    @Suppress("DEPRECATION")
                    gatt.writeCharacteristic(ackChar)
                }
            }
        }
    }
}
