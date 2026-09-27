/*
 * ESP32 Classroom BLE Beacon Transmitter
 * 
 * Project: IERT Smart Attendance System
 * Target Hardware: ESP32 Dev Module / NodeMCU-32S / ESP-WROOM-32
 * 
 * This firmware turns an ESP32 into a BLE Classroom Beacon.
 * When students enter the classroom with the Android App, their phone detects this
 * beacon and unlocks the attendance scan:
 * "Beacon Detected. Tap to mark attendance."
 * 
 * CONFIGURATION:
 * 1. Private settings are loaded from "beacon_config.h" (ignored by git).
 * 2. If not present, fallback settings are loaded from "beacon_config.h.example".
 */

#include <Arduino.h>
#include "BLEDevice.h"
#include "BLEUtils.h"
#include "BLEServer.h"
#include "BLEBeacon.h"
#include "esp_sleep.h"

// ----------------------------------------------------------------------------
// Configuration Loader
// ----------------------------------------------------------------------------
#if __has_include("beacon_config.h")
    #include "beacon_config.h"
#elif __has_include("beacon_config.h.example")
    #include "beacon_config.h.example"
#else
    #define BEACON_UUID       "00000000-0000-0000-0000-000000000000"
    #define BEACON_UUID_REV   "00000000-0000-0000-0000-000000000000"
    #define BEACON_NAME       "SAS_Classroom_Beacon"
    #define LED_PIN           2
#endif

BLEAdvertising *pAdvertising;

void setBeacon() {
    BLEBeacon oBeacon = BLEBeacon();
    oBeacon.setManufacturerId(0x4C00); // Apple iBeacon format (0x004C)
    
    // Set UUID (using reversed byte string so broadcasted packet matches BEACON_UUID exactly)
    oBeacon.setProximityUUID(BLEUUID(BEACON_UUID_REV));
    oBeacon.setMajor(1);         // Room / Classroom number (e.g. Room 1)
    oBeacon.setMinor(101);       // Section / Sub-room (e.g. 101)
    oBeacon.setSignalPower(-59); // Measured RSSI power at 1 meter

    BLEAdvertisementData oAdvertisementData;
    BLEAdvertisementData oScanResponseData;

    oAdvertisementData.setFlags(0x04); // BR_EDR_NOT_SUPPORTED 0x04 (BLE Only)

    /*
     * ESP32 Arduino Core 3.x (v3.3.11+):
     * oBeacon.getData() returns Arduino String with the full 25-byte binary iBeacon structure.
     * oAdvertisementData.setManufacturerData() automatically attaches the length byte (26)
     * and manufacturer-specific AD type (0xFF), ensuring 100% standard iBeacon compatibility.
     */
    oAdvertisementData.setManufacturerData(oBeacon.getData());
    oScanResponseData.setName(BEACON_NAME);

    pAdvertising->setAdvertisementData(oAdvertisementData);
    pAdvertising->setScanResponseData(oScanResponseData);
    pAdvertising->setScanResponse(true);
}

void setup() {
    Serial.begin(115200);
    delay(500);

    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, HIGH);

    Serial.println("\n==========================================");
    Serial.println("  IERT Smart Attendance - Classroom Beacon");
    Serial.println("==========================================");
    Serial.printf("Broadcasting UUID : %s\n", BEACON_UUID);
    Serial.printf("Beacon Name       : %s\n", BEACON_NAME);
    Serial.printf("Major / Minor     : 1 / 101\n");
    Serial.println("Status            : Active & Transmitting");
    Serial.println("==========================================\n");

    // Initialize BLE Device
    BLEDevice::init(BEACON_NAME);
    pAdvertising = BLEDevice::getAdvertising();

    setBeacon();

    // Start advertising
    pAdvertising->start();
    Serial.println("[BLE] Beacon is now LIVE. Students' phones will detect it automatically.\n");
}

void loop() {
    // Heartbeat: blink onboard LED every 3 seconds to indicate healthy beacon transmission
    digitalWrite(LED_PIN, HIGH);
    delay(100);
    digitalWrite(LED_PIN, LOW);
    delay(2900);
}