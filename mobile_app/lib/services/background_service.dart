import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../utils/constants.dart';
import '../services/background_service.dart';
import '../screens/register_screen.dart';
import '../screens/attendance_screen.dart';
import '../screens/face_scan_screen.dart';
import '../screens/analytics_screen.dart';
Future<void> initializeBackgroundService() async {
  final service = FlutterBackgroundService();

  await service.configure(
    androidConfiguration: AndroidConfiguration(
      onStart: onBackgroundServiceStart,
      autoStart: false,
      isForegroundMode: false,
      notificationChannelId: kNotificationChannelId,
      initialNotificationTitle: 'Smart Attendance Service',
      initialNotificationContent: 'Monitoring classroom beacons in background...',
      foregroundServiceNotificationId: kForegroundServiceNotificationId,
    ),
    iosConfiguration: IosConfiguration(
      autoStart: false,
      onForeground: onBackgroundServiceStart,
      onBackground: onIosBackground,
    ),
  );
}

@pragma('vm:entry-point')
Future<bool> onIosBackground(ServiceInstance service) async {
  WidgetsFlutterBinding.ensureInitialized();
  DartPluginRegistrant.ensureInitialized();
  return true;
}

@pragma('vm:entry-point')
void onBackgroundServiceStart(ServiceInstance service) async {
  DartPluginRegistrant.ensureInitialized();

  if (service is AndroidServiceInstance) {
    service.on('setAsForeground').listen((event) {
      service.setAsForegroundService();
    });
    service.setAsForegroundService();
  }

  service.on('stopService').listen((event) {
    service.stopSelf();
  });

  final cleanTargetUUID = kBeaconUUID.replaceAll('-', '').toLowerCase();
  DateTime? lastNotificationTime;

  Timer.periodic(const Duration(seconds: 15), (timer) async {
    try {
      if (lastNotificationTime != null &&
          DateTime.now().difference(lastNotificationTime!).inMinutes < 5) {
        return;
      }

      final isScanning = FlutterBluePlus.isScanningNow;
      if (isScanning) return;

      bool foundBeacon = false;
      final completer = Completer<bool>();

      final subscription = FlutterBluePlus.scanResults.listen((results) {
        for (final result in results) {
          bool matched = false;

          for (final serviceUuid in result.advertisementData.serviceUuids) {
            final cleanUuid =
                serviceUuid.toString().replaceAll('-', '').toLowerCase();
            if (cleanUuid == cleanTargetUUID) {
              matched = true;
              break;
            }
          }

          if (!matched) {
            final mfgData = result.advertisementData.manufacturerData;
            if (mfgData.containsKey(0x004C) || mfgData.containsKey(0x4C00)) {
              final bytes = mfgData[0x004C] ?? mfgData[0x4C00];
              if (bytes != null && bytes.length >= 20) {
                final uuidBytes = bytes.sublist(2, 18);
                final hexStr = uuidBytes
                    .map((b) => b.toRadixString(16).padLeft(2, '0'))
                    .join();
                if (hexStr == cleanTargetUUID) {
                  matched = true;
                }
              }
            }
          }

          if (!matched) {
            final name = result.advertisementData.advName;
            if (name.isNotEmpty &&
                (name.contains('Classroom_Beacon') || name.contains('SAS_Classroom_Beacon'))) {
              matched = true;
            }
          }

          if (matched && result.rssi >= kMinRssi) {
            completer.complete(true);
          }
        }
      });

      await FlutterBluePlus.startScan(
        timeout: const Duration(seconds: 6),
        androidUsesFineLocation: true,
      );

      foundBeacon = await completer.future.timeout(
        const Duration(seconds: 7),
        onTimeout: () => false,
      );

      await FlutterBluePlus.stopScan();
      await subscription.cancel();

      if (foundBeacon) {
        lastNotificationTime = DateTime.now();
        await showClassroomNotification();
        service.invoke('beaconDetected', {'time': DateTime.now().toIso8601String()});
      }
    } catch (e) {
      debugPrint('[BackgroundService] Scan error: $e');
    }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
//  App Entry Point
// ─────────────────────────────────────────────────────────────────────────────

