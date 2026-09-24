import '../screens/face_scan_screen.dart';
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

// ─────────────────────────────────────────────────────────────────────────────
//  Configuration & Constants
// ─────────────────────────────────────────────────────────────────────────────

/// The iBeacon Proximity UUID broadcast by the classroom ESP32 beacon.
/// Must match the value flashed onto the ESP32.
const String kBeaconUUID = '12345678-1234-1234-1234-123456789abc';

/// Minimum RSSI (in dBm) to consider student inside the classroom.
const int kMinRssi = -75;

/// How long to scan for the beacon before giving up during manual scan.
const Duration kScanTimeout = Duration(seconds: 8);

/// Default Backend URL (fallback when not configured by user)
const String kDefaultApiBaseUrl = 'https://ayush-smart-backend.loca.lt';

/// Local Push Notification Channel IDs
const String kNotificationChannelId = 'classroom_ble_channel';
const String kNotificationChannelName = 'Classroom Beacon Alerts';
const int kClassroomNotificationId = 888;
const int kForegroundServiceNotificationId = 889;

/// College Branches & Sections Mapping
const Map<String, String> kBranches = {
  'A': 'Computer Science & Engineering',
  'B': 'Electronics Engineering',
  'C': 'Industrial & Production Engineering',
  'D': 'Mechanical Engineering',
  'E': 'Instrumentation & Control Engineering',
  'F': 'Electrical Engineering',
  'G': 'Civil Engineering',
};

const Map<String, String> kBranchShortNames = {
  'A': 'CSE',
  'B': 'ECE',
  'C': 'IPE',
  'D': 'ME',
  'E': 'ICE',
  'F': 'EE',
  'G': 'CE',
};

Map<String, String> get kDefaultHttpHeaders => {
  'Bypass-Tunnel-Reminder': 'true',
  'Accept': 'application/json',
  'User-Agent': 'SmartAttendanceApp/1.0',
  'X-API-Key': 'iert_sas_secure_key_2026',
};

// ─────────────────────────────────────────────────────────────────────────────
//  Global State & Navigation
// ─────────────────────────────────────────────────────────────────────────────


late List<CameraDescription> globalCameras;
final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();
final FlutterLocalNotificationsPlugin _localNotifications =
    FlutterLocalNotificationsPlugin();

/// Broadcast stream to trigger face scan screen when notification is tapped
final StreamController<bool> globalFaceScanTrigger =
    StreamController<bool>.broadcast();

// ─────────────────────────────────────────────────────────────────────────────
//  Profile & Settings Storage Helpers
// ─────────────────────────────────────────────────────────────────────────────

class AppSettings {
  static const String keyIsRegistered = 'is_registered';
  static const String keyStudentName = 'student_name';
  static const String keyStudentRoll = 'student_roll';
  static const String keyServerUrl = 'server_url';
  static const String keyStudentBranch = 'student_branch';
  static const String keyStudentSection = 'student_section';
  static const String keyStudentClassRoll = 'student_class_roll';
  static const String keyStudentYear = 'student_year';

  static String getYearLabel(dynamic yearOrSection) {
    if (yearOrSection == null) return '1st Year';
    final str = yearOrSection.toString().trim().toUpperCase();
    if (str.isEmpty) return '1st Year';
    if (str == '1' || str.endsWith('1')) return '1st Year';
    if (str == '2' || str.endsWith('2')) return '2nd Year';
    if (str == '3' || str.endsWith('3')) return '3rd Year';
    if (str == '4' || str.endsWith('4')) return '4th Year';
    return '$str Year';
  }

  static Future<bool> isRegistered() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(keyIsRegistered) ?? false;
  }

  static Future<String> getStudentName() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(keyStudentName) ?? '';
  }

  static Future<String> getStudentRoll() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(keyStudentRoll) ?? '';
  }

  static Future<String> getStudentBranch() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(keyStudentBranch) ?? '';
  }

  static Future<String> getStudentSection() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(keyStudentSection) ?? '';
  }

  static Future<String> getStudentClassRoll() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(keyStudentClassRoll) ?? '';
  }

  static Future<String> getStudentYear() async {
    final prefs = await SharedPreferences.getInstance();
    final yr = prefs.getString(keyStudentYear) ?? '';
    if (yr.isNotEmpty) return yr;
    final sec = prefs.getString(keyStudentSection) ?? '';
    if (sec.length >= 2 && RegExp(r'^[1-4]$').hasMatch(sec.substring(1))) {
      return sec.substring(1);
    }
    return '';
  }

  static Future<String> getServerUrl() async {
    final prefs = await SharedPreferences.getInstance();
    final url = prefs.getString(keyServerUrl);
    if (url == null || url.trim().isEmpty || url.contains('localhost') || url.contains('127.0.0.1')) {
      return kDefaultApiBaseUrl;
    }
    return url.trim();
  }

  static Future<void> saveProfile({
    required String name,
    required String rollNo,
    required String serverUrl,
    String branch = '',
    String section = '',
    String classRoll = '',
    String year = '',
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(keyIsRegistered, true);
    await prefs.setString(keyStudentName, name);
    await prefs.setString(keyStudentRoll, rollNo);
    await prefs.setString(keyServerUrl, serverUrl);
    await prefs.setString(keyStudentBranch, branch);
    await prefs.setString(keyStudentSection, section);
    await prefs.setString(keyStudentClassRoll, classRoll);

    String finalYear = year;
    if (finalYear.isEmpty && section.length >= 2 && RegExp(r'^[1-4]$').hasMatch(section.substring(1))) {
      finalYear = section.substring(1);
    }
    await prefs.setString(keyStudentYear, finalYear);
  }

  static Future<void> updateServerUrl(String serverUrl) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(keyServerUrl, serverUrl);
  }

  static const String keyDeviceId = 'device_hardware_uuid';

  static Future<String> getDeviceId() async {
    final prefs = await SharedPreferences.getInstance();
    String? devId = prefs.getString(keyDeviceId);
    if (devId == null || devId.isEmpty) {
      devId = 'dev_${DateTime.now().millisecondsSinceEpoch}_${(1000 + (DateTime.now().microsecond % 9000))}';
      await prefs.setString(keyDeviceId, devId);
    }
    return devId;
  }

  static Future<void> clearProfile() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(keyIsRegistered);
    await prefs.remove(keyStudentName);
    await prefs.remove(keyStudentRoll);
    await prefs.remove(keyStudentBranch);
    await prefs.remove(keyStudentSection);
    await prefs.remove(keyStudentClassRoll);
    await prefs.remove(keyStudentYear);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Local Push Notification Setup
// ─────────────────────────────────────────────────────────────────────────────

Future<void> initLocalNotifications() async {
  const AndroidInitializationSettings androidSettings =
      AndroidInitializationSettings('@mipmap/ic_launcher');

  const DarwinInitializationSettings darwinSettings =
      DarwinInitializationSettings(
    requestAlertPermission: true,
    requestBadgePermission: true,
    requestSoundPermission: true,
  );

  const InitializationSettings initSettings = InitializationSettings(
    android: androidSettings,
    iOS: darwinSettings,
  );

  await _localNotifications.initialize(
    initSettings,
    onDidReceiveNotificationResponse: (NotificationResponse response) {
      if (response.payload == 'open_face_scan') {
        _navigateToFaceScanScreen();
      }
    },
  );

  final androidPlugin = _localNotifications
      .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>();
  if (androidPlugin != null) {
    await androidPlugin.createNotificationChannel(
      const AndroidNotificationChannel(
        kNotificationChannelId,
        kNotificationChannelName,
        description: 'Notifies when ESP32 classroom beacon is detected nearby',
        importance: Importance.max,
        playSound: true,
      ),
    );
  }
}

/// Triggers the Local Push Notification:
/// "You are in the classroom. Tap to mark attendance."
Future<void> showClassroomNotification() async {
  const AndroidNotificationDetails androidDetails = AndroidNotificationDetails(
    kNotificationChannelId,
    kNotificationChannelName,
    channelDescription:
        'Notifies when ESP32 classroom beacon is detected nearby',
    importance: Importance.max,
    priority: Priority.high,
    icon: '@mipmap/ic_launcher',
    ticker: 'Classroom detected',
  );

  const DarwinNotificationDetails darwinDetails = DarwinNotificationDetails(
    presentAlert: true,
    presentBadge: true,
    presentSound: true,
  );

  const NotificationDetails notificationDetails = NotificationDetails(
    android: androidDetails,
    iOS: darwinDetails,
  );

  await _localNotifications.show(
    kClassroomNotificationId,
    'Smart Attendance',
    'You are in the classroom. Tap to mark attendance.',
    notificationDetails,
    payload: 'open_face_scan',
  );
}

void _navigateToFaceScanScreen() {
  debugPrint('[NOTIFICATION] Notification tapped -> Opening Face Scan Screen');
  globalFaceScanTrigger.add(true);
  navigatorKey.currentState?.push(
    MaterialPageRoute(
      builder: (context) => const FaceScanScreen(),
    ),
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  Background BLE Service
// ─────────────────────────────────────────────────────────────────────────────



const String kApiKey = 'iert_sas_secure_key_2026';
