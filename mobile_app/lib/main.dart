import 'dart:async';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'utils/constants.dart';
import 'services/background_service.dart';
import 'screens/register_screen.dart';
import 'screens/attendance_screen.dart';
import 'screens/face_scan_screen.dart';
import 'screens/analytics_screen.dart';
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();


  try {
    globalCameras = await availableCameras();
  } catch (e) {
    globalCameras = [];
    debugPrint('[CAMERA] Initialization error: $e');
  }

  try {
    await initLocalNotifications();
    await initializeBackgroundService();
    
    // Explicitly kill the background service if it was running from a previous installation
    final service = FlutterBackgroundService();
    if (await service.isRunning()) {
      service.invoke("stopService");
    }
  } catch (e) {
    debugPrint('[BACKGROUND SERVICE] Initialization error: $e');
  }

  final bool alreadyRegistered = await AppSettings.isRegistered();

  runApp(AttendanceApp(isRegistered: alreadyRegistered));
}

// ─────────────────────────────────────────────────────────────────────────────
//  Root Widget
// ─────────────────────────────────────────────────────────────────────────────

class AttendanceApp extends StatelessWidget {
  final bool isRegistered;
  const AttendanceApp({super.key, required this.isRegistered});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: navigatorKey,
      title: 'Smart Attendance',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF0F3460),
        useMaterial3: true,
        brightness: Brightness.light,
        scaffoldBackgroundColor: const Color(0xFFF4F6F9),
      ),
      home: isRegistered
          ? const AttendanceScreen()
          : const StudentRegisterScreen(),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  1st-Time Student Registration Screen
// ─────────────────────────────────────────────────────────────────────────────

