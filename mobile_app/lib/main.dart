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
const String kDefaultApiBaseUrl = 'http://10.127.162.188:8000';

/// Local Push Notification Channel IDs
const String kNotificationChannelId = 'classroom_ble_channel';
const String kNotificationChannelName = 'Classroom Beacon Alerts';
const int kClassroomNotificationId = 888;
const int kForegroundServiceNotificationId = 889;

// ─────────────────────────────────────────────────────────────────────────────
//  Global State & Navigation
// ─────────────────────────────────────────────────────────────────────────────

late List<CameraDescription> _cameras;
final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();
final FlutterLocalNotificationsPlugin _localNotifications =
    FlutterLocalNotificationsPlugin();

/// Broadcast stream to trigger face scan screen when notification is tapped
final StreamController<bool> _openFaceScanTrigger =
    StreamController<bool>.broadcast();

// ─────────────────────────────────────────────────────────────────────────────
//  Profile & Settings Storage Helpers
// ─────────────────────────────────────────────────────────────────────────────

class AppSettings {
  static const String keyIsRegistered = 'is_registered';
  static const String keyStudentName = 'student_name';
  static const String keyStudentRoll = 'student_roll';
  static const String keyServerUrl = 'server_url';

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

  static Future<String> getServerUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(keyServerUrl) ?? kDefaultApiBaseUrl;
  }

  static Future<void> saveProfile({
    required String name,
    required String rollNo,
    required String serverUrl,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(keyIsRegistered, true);
    await prefs.setString(keyStudentName, name);
    await prefs.setString(keyStudentRoll, rollNo);
    await prefs.setString(keyServerUrl, serverUrl);
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
  _openFaceScanTrigger.add(true);
  navigatorKey.currentState?.push(
    MaterialPageRoute(
      builder: (context) => const FaceScanScreen(),
    ),
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  Background BLE Service
// ─────────────────────────────────────────────────────────────────────────────

Future<void> initializeBackgroundService() async {
  final service = FlutterBackgroundService();

  await service.configure(
    androidConfiguration: AndroidConfiguration(
      onStart: onBackgroundServiceStart,
      autoStart: true,
      isForegroundMode: true,
      notificationChannelId: kNotificationChannelId,
      initialNotificationTitle: 'Smart Attendance Service',
      initialNotificationContent: 'Monitoring classroom beacons in background...',
      foregroundServiceNotificationId: kForegroundServiceNotificationId,
    ),
    iosConfiguration: IosConfiguration(
      autoStart: true,
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

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  try {
    _cameras = await availableCameras();
  } catch (e) {
    _cameras = [];
    debugPrint('[CAMERA] Initialization error: $e');
  }

  await initLocalNotifications();
  await initializeBackgroundService();

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

class StudentRegisterScreen extends StatefulWidget {
  final bool isEditMode;
  const StudentRegisterScreen({super.key, this.isEditMode = false});

  @override
  State<StudentRegisterScreen> createState() => _StudentRegisterScreenState();
}

class _StudentRegisterScreenState extends State<StudentRegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _rollController = TextEditingController();
  final _serverController = TextEditingController(text: kDefaultApiBaseUrl);

  CameraController? _cameraController;
  bool _isCameraReady = false;
  XFile? _capturedFacePhoto;
  bool _isRegistering = false;
  bool _isRestoring = false;

  @override
  void initState() {
    super.initState();
    _loadExistingProfile();
    _initializeCamera();
  }

  Future<void> _loadExistingProfile() async {
    final server = await AppSettings.getServerUrl();
    _serverController.text = server;

    if (widget.isEditMode) {
      _nameController.text = await AppSettings.getStudentName();
      _rollController.text = await AppSettings.getStudentRoll();
    }
  }

  Future<void> _initializeCamera() async {
    if (_cameras.isEmpty) {
      try {
        _cameras = await availableCameras();
      } catch (e) {
        debugPrint('[Camera] Init error: $e');
        return;
      }
    }

    CameraDescription? frontCamera;
    for (final cam in _cameras) {
      if (cam.lensDirection == CameraLensDirection.front) {
        frontCamera = cam;
        break;
      }
    }
    frontCamera ??= _cameras.isNotEmpty ? _cameras.first : null;

    if (frontCamera == null) return;

    final controller = CameraController(
      frontCamera,
      ResolutionPreset.medium,
      enableAudio: false,
    );

    try {
      await controller.initialize();
      if (!mounted) return;
      setState(() {
        _cameraController = controller;
        _isCameraReady = true;
      });
    } catch (e) {
      debugPrint('[Camera] Error: $e');
    }
  }

  Future<void> _capturePhoto() async {
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      return;
    }
    try {
      final photo = await _cameraController!.takePicture();
      setState(() {
        _capturedFacePhoto = photo;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error capturing photo: $e')),
        );
      }
    }
  }

  Future<void> _submitRegistration() async {
    if (!_formKey.currentState!.validate()) return;

    if (_capturedFacePhoto == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please capture a face selfie photo first.'),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    setState(() => _isRegistering = true);

    final name = _nameController.text.trim();
    final rollNo = _rollController.text.trim().toUpperCase();
    final serverUrl = _serverController.text.trim();

    try {
      final deviceId = await AppSettings.getDeviceId();
      final uri = Uri.parse('$serverUrl/register');
      final request = http.MultipartRequest('POST', uri)
        ..fields['name'] = name
        ..fields['roll_no'] = rollNo
        ..fields['device_id'] = deviceId
        ..files.add(
          await http.MultipartFile.fromPath(
            'photo',
            _capturedFacePhoto!.path,
          ),
        );

      final streamed = await request.send().timeout(const Duration(seconds: 15));
      final response = await http.Response.fromStream(streamed);

      final Map<String, dynamic> data =
          jsonDecode(response.body) as Map<String, dynamic>;

      if (response.statusCode == 200 || response.statusCode == 201) {
        // Save locally in SharedPreferences
        await AppSettings.saveProfile(
          name: name,
          rollNo: rollNo,
          serverUrl: serverUrl,
        );

        if (!mounted) return;

        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (ctx) => AlertDialog(
            icon: const Icon(Icons.check_circle, color: Colors.green, size: 50),
            title: const Text('Registration Successful!'),
            content: Text(
              'Welcome $name!\n\nYour profile (Roll: $rollNo) and face encoding have been saved on the server.\n\nYou can now mark attendance anytime you are in class.',
            ),
            actions: [
              FilledButton(
                onPressed: () {
                  Navigator.of(ctx).pop();
                  Navigator.of(context).pushReplacement(
                    MaterialPageRoute(
                      builder: (context) => const AttendanceScreen(),
                    ),
                  );
                },
                child: const Text('Go to Dashboard'),
              ),
            ],
          ),
        );
      } else {
        final errorMsg = data['detail'] ?? 'Registration failed (${response.statusCode})';
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Server Error: $errorMsg'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } on SocketException {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Cannot connect to server at $serverUrl.\nPlease ensure Phone and Laptop are on the same Wi-Fi / Hotspot.'),
          backgroundColor: Colors.red,
          duration: const Duration(seconds: 5),
        ),
      );
    } on TimeoutException {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Connection timed out to $serverUrl.\nCheck if Laptop IP is correct (e.g. http://10.127.162.188:8000) and backend server is running.'),
          backgroundColor: Colors.red,
          duration: const Duration(seconds: 6),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) setState(() => _isRegistering = false);
    }
  }

  Future<void> _restoreExistingProfile() async {
    final rollNo = _rollController.text.trim().toUpperCase();
    final serverUrl = _serverController.text.trim();

    if (rollNo.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please enter your Roll Number first to restore profile.'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }
    if (serverUrl.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please enter Server Base URL.'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    setState(() => _isRestoring = true);
    try {
      final uri = Uri.parse('$serverUrl/students/$rollNo');
      final response = await http.get(uri).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final studentName = data['name'] ?? 'Student';
        final studentRoll = data['roll_no'] ?? rollNo;

        await AppSettings.saveProfile(
          name: studentName,
          rollNo: studentRoll,
          serverUrl: serverUrl,
        );

        if (!mounted) return;
        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (ctx) => AlertDialog(
            icon: const Icon(Icons.verified_user, color: Colors.green, size: 50),
            title: const Text('Profile Restored!'),
            content: Text(
              'Welcome back, $studentName!\n\nYour profile (Roll: $studentRoll) is active on the server. You can now mark attendance.',
            ),
            actions: [
              FilledButton(
                onPressed: () {
                  Navigator.of(ctx).pop();
                  Navigator.of(context).pushReplacement(
                    MaterialPageRoute(
                      builder: (context) => const AttendanceScreen(),
                    ),
                  );
                },
                child: const Text('Go to Dashboard'),
              ),
            ],
          ),
        );
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Roll No "$rollNo" is not registered yet. Please enter your name, take a selfie, and tap "Register Student" below.'),
            backgroundColor: Colors.red,
            duration: const Duration(seconds: 5),
          ),
        );
      }
    } on SocketException {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Cannot connect to server at $serverUrl.\nCheck Wi-Fi / IP connection.'),
          backgroundColor: Colors.red,
        ),
      );
    } on TimeoutException {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Connection timed out to $serverUrl.\nCheck if backend server is running.'),
          backgroundColor: Colors.red,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
      );
    } finally {
      if (mounted) setState(() => _isRestoring = false);
    }
  }

  @override
  void dispose() {
    _cameraController?.dispose();
    _nameController.dispose();
    _rollController.dispose();
    _serverController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.isEditMode ? 'Edit Student Profile' : 'Student Registration'),
        centerTitle: true,
        backgroundColor: const Color(0xFF16213E),
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Header Info
                Card(
                  elevation: 0,
                  color: const Color(0xFF0F3460).withValues(alpha: 0.08),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: const BorderSide(color: Color(0xFF0F3460), width: 0.5),
                  ),
                  child: const Padding(
                    padding: EdgeInsets.all(14),
                    child: Row(
                      children: [
                        Icon(Icons.info_outline, color: Color(0xFF0F3460)),
                        SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            'Register your name, roll number, and face profile once. The app will save your details for attendance.',
                            style: TextStyle(fontSize: 13, height: 1.3),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 18),

                // Name input
                TextFormField(
                  controller: _nameController,
                  decoration: InputDecoration(
                    labelText: 'Full Name',
                    hintText: 'e.g. Ayush Pandey',
                    prefixIcon: const Icon(Icons.person),
                    filled: true,
                    fillColor: Colors.white,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  validator: (v) =>
                      v == null || v.trim().isEmpty ? 'Please enter your name' : null,
                ),
                const SizedBox(height: 14),

                // Roll Number input
                TextFormField(
                  controller: _rollController,
                  decoration: InputDecoration(
                    labelText: 'Roll Number / Student ID',
                    hintText: 'e.g. CS-2024-001',
                    prefixIcon: const Icon(Icons.badge),
                    filled: true,
                    fillColor: Colors.white,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  validator: (v) =>
                      v == null || v.trim().isEmpty ? 'Please enter roll number' : null,
                ),
                const SizedBox(height: 14),

                // Server URL input
                TextFormField(
                  controller: _serverController,
                  decoration: InputDecoration(
                    labelText: 'Server Base URL',
                    hintText: 'http://<LAPTOP_IP>:8000',
                    prefixIcon: const Icon(Icons.dns),
                    helperText: 'Laptop & Phone same Wi-Fi pe honi chahiye (e.g. http://10.127.162.188:8000)',
                    helperMaxLines: 2,
                    filled: true,
                    fillColor: Colors.white,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  validator: (v) =>
                      v == null || v.trim().isEmpty ? 'Please enter server URL' : null,
                ),
                const SizedBox(height: 12),

                // Restore Profile action for re-installed app
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0F3460).withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: const Color(0xFF0F3460).withValues(alpha: 0.2)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.history, color: Color(0xFF0F3460), size: 20),
                      const SizedBox(width: 8),
                      const Expanded(
                        child: Text(
                          'App reinstalled? Restore with Roll No:',
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                        ),
                      ),
                      FilledButton.tonal(
                        onPressed: _isRestoring ? null : _restoreExistingProfile,
                        child: _isRestoring
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Text('Restore Profile', style: TextStyle(fontSize: 12)),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),

                // Face Photo Capture Section
                Text(
                  'Face Photo Registration',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),

                Container(
                  height: 260,
                  decoration: BoxDecoration(
                    color: Colors.black,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: _capturedFacePhoto != null
                      ? Stack(
                          fit: StackFit.expand,
                          children: [
                            Image.file(
                              File(_capturedFacePhoto!.path),
                              fit: BoxFit.cover,
                            ),
                            Positioned(
                              bottom: 12,
                              right: 12,
                              child: FilledButton.tonalIcon(
                                onPressed: () {
                                  setState(() => _capturedFacePhoto = null);
                                },
                                icon: const Icon(Icons.refresh),
                                label: const Text('Retake Photo'),
                              ),
                            ),
                          ],
                        )
                      : _isCameraReady && _cameraController != null
                          ? Stack(
                              alignment: Alignment.center,
                              children: [
                                CameraPreview(_cameraController!),
                                Container(
                                  width: 170,
                                  height: 220,
                                  decoration: BoxDecoration(
                                    borderRadius: BorderRadius.circular(90),
                                    border: Border.all(
                                      color: Colors.white.withValues(alpha: 0.8),
                                      width: 2.5,
                                    ),
                                  ),
                                ),
                                Positioned(
                                  bottom: 12,
                                  child: FilledButton.icon(
                                    onPressed: _capturePhoto,
                                    icon: const Icon(Icons.camera_alt),
                                    label: const Text('Capture Face'),
                                  ),
                                ),
                              ],
                            )
                          : const Center(
                              child: CircularProgressIndicator(color: Colors.white),
                            ),
                ),
                const SizedBox(height: 24),

                // Submit Button
                SizedBox(
                  height: 54,
                  child: FilledButton.icon(
                    onPressed: _isRegistering ? null : _submitRegistration,
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFFE94560),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    icon: _isRegistering
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2.5,
                            ),
                          )
                        : const Icon(Icons.how_to_reg, size: 24),
                    label: Text(
                      _isRegistering ? 'Registering Face…' : 'Register Profile & Face',
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
                const SizedBox(height: 20),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Main Attendance Dashboard (For Registered Students)
// ─────────────────────────────────────────────────────────────────────────────

class AttendanceScreen extends StatefulWidget {
  const AttendanceScreen({super.key});

  @override
  State<AttendanceScreen> createState() => _AttendanceScreenState();
}

class _AttendanceScreenState extends State<AttendanceScreen> {
  StreamSubscription<bool>? _notificationSub;
  Timer? _autoRefreshTimer;

  String _studentName = '';
  String _studentRoll = '';
  String _serverUrl = '';

  // Timetable State
  bool _isLoadingTimetable = false;
  Map<String, dynamic>? _currentClass;
  Map<String, dynamic>? _windowStatus;
  String _serverDay = '';
  String _serverTime = '';

  // BLE Beacon State
  bool _isManualScanning = false;
  bool _isBeaconDetected = false;
  int? _beaconRssi;
  String _beaconName = '';
  String _bleStatusMessage = 'Waiting for classroom beacon scan...';

  @override
  void initState() {
    super.initState();
    _loadProfile();
    _requestAllPermissions();

    _notificationSub = _openFaceScanTrigger.stream.listen((shouldOpen) {
      if (shouldOpen && mounted) {
        // Handled globally
      }
    });

    // Auto-refresh timetable and beacon every 15 seconds
    _autoRefreshTimer = Timer.periodic(const Duration(seconds: 15), (_) {
      if (mounted && !_isManualScanning) {
        _fetchLiveTimetable();
      }
    });
  }

  Future<void> _loadProfile() async {
    final name = await AppSettings.getStudentName();
    final roll = await AppSettings.getStudentRoll();
    final server = await AppSettings.getServerUrl();
    if (mounted) {
      setState(() {
        _studentName = name;
        _studentRoll = roll;
        _serverUrl = server;
      });
      _fetchLiveTimetable();
      _startManualBeaconScan();
    }
  }

  @override
  void dispose() {
    _autoRefreshTimer?.cancel();
    _notificationSub?.cancel();
    super.dispose();
  }

  Future<void> _requestAllPermissions() async {
    await [
      Permission.bluetooth,
      Permission.bluetoothScan,
      Permission.bluetoothConnect,
      Permission.locationWhenInUse,
      Permission.locationAlways,
      Permission.camera,
      Permission.notification,
    ].request();
  }

  Future<void> _fetchLiveTimetable() async {
    if (_serverUrl.isEmpty) return;
    setState(() => _isLoadingTimetable = true);
    try {
      final uri = Uri.parse('$_serverUrl/timetable');
      final response = await http.get(uri).timeout(const Duration(seconds: 8));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final currentSlot = data['current_slot'] as Map<String, dynamic>?;
        if (currentSlot != null && mounted) {
          setState(() {
            _serverDay = currentSlot['day'] ?? '';
            _serverTime = currentSlot['time'] ?? '';
            _currentClass = currentSlot['class'] as Map<String, dynamic>?;
            _windowStatus = currentSlot['window_status'] as Map<String, dynamic>?;
          });
        }
      }
    } catch (e) {
      debugPrint('[TIMETABLE] Failed to fetch: $e');
    } finally {
      if (mounted) setState(() => _isLoadingTimetable = false);
    }
  }

  Future<void> _startManualBeaconScan() async {
    if (_isManualScanning) return;
    setState(() {
      _isManualScanning = true;
      _bleStatusMessage = 'Scanning for ESP32 Classroom Beacon...';
    });

    final cleanTargetUUID = kBeaconUUID.replaceAll('-', '').toLowerCase();
    bool found = false;
    int? bestRssi;
    String detectedName = '';

    StreamSubscription? scanSub;
    try {
      // Check Bluetooth Adapter
      if (await FlutterBluePlus.adapterState.first != BluetoothAdapterState.on) {
        setState(() {
          _isBeaconDetected = false;
          _bleStatusMessage = 'Please turn ON Bluetooth on your phone.';
          _isManualScanning = false;
        });
        return;
      }

      scanSub = FlutterBluePlus.scanResults.listen((results) {
        for (final r in results) {
          bool matched = false;

          // 1. Service UUID match
          for (final u in r.advertisementData.serviceUuids) {
            final clean = u.toString().replaceAll('-', '').toLowerCase();
            if (clean == cleanTargetUUID) {
              matched = true;
              break;
            }
          }

          // 2. iBeacon Manufacturer match
          if (!matched) {
            final mfg = r.advertisementData.manufacturerData;
            if (mfg.containsKey(0x004C) || mfg.containsKey(0x4C00)) {
              final bytes = mfg[0x004C] ?? mfg[0x4C00];
              if (bytes != null && bytes.length >= 20) {
                final uuidBytes = bytes.sublist(2, 18);
                final hexStr = uuidBytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
                if (hexStr == cleanTargetUUID) {
                  matched = true;
                }
              }
            }
          }

          // 3. Name match
          if (!matched) {
            final name = r.advertisementData.advName;
            final devName = r.device.platformName;
            if (name.contains('Classroom_Beacon') ||
                name.contains('SAS_Classroom_Beacon') ||
                devName.contains('Classroom_Beacon') ||
                devName.contains('SAS_Classroom_Beacon')) {
              matched = true;
            }
          }

          if (matched) {
            found = true;
            bestRssi = r.rssi;
            detectedName = r.advertisementData.advName.isNotEmpty
                ? r.advertisementData.advName
                : (r.device.platformName.isNotEmpty ? r.device.platformName : 'SAS_Classroom_Beacon');
            break;
          }
        }
      });

      await FlutterBluePlus.startScan(
        timeout: const Duration(seconds: 6),
        androidUsesFineLocation: true,
      );

      await Future.delayed(const Duration(seconds: 6));
    } catch (e) {
      debugPrint('[BLE_SCAN] Error: $e');
      setState(() => _bleStatusMessage = 'Scan error: $e');
    } finally {
      await FlutterBluePlus.stopScan();
      await scanSub?.cancel();
      if (mounted) {
        setState(() {
          _isManualScanning = false;
          _isBeaconDetected = found;
          _beaconRssi = bestRssi;
          _beaconName = detectedName;
          if (found) {
            _bleStatusMessage = 'ESP32 Beacon detected! Signal: ${bestRssi ?? 0} dBm';
          } else {
            _bleStatusMessage = 'Beacon not detected. Ensure ESP32 is ON & Location is active.';
          }
        });
      }
    }
  }

  void _showSettingsDialog() {
    final controller = TextEditingController(text: _serverUrl);

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Server & Profile Settings'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Server Address:',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
            ),
            const SizedBox(height: 6),
            TextField(
              controller: controller,
              decoration: const InputDecoration(
                hintText: 'http://10.127.162.188:8000',
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
            const SizedBox(height: 18),
            const Divider(),
            const SizedBox(height: 6),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.edit, color: Color(0xFF0F3460)),
              title: const Text('Edit Student Profile'),
              subtitle: const Text('Change name, roll number, or photo'),
              onTap: () {
                Navigator.of(ctx).pop();
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (context) => const StudentRegisterScreen(isEditMode: true),
                  ),
                ).then((_) => _loadProfile());
              },
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.logout, color: Colors.red),
              title: const Text('Reset Profile / Switch User'),
              onTap: () async {
                final nav = Navigator.of(context);
                final rootNav = Navigator.of(ctx);
                await AppSettings.clearProfile();
                rootNav.pop();
                nav.pushReplacement(
                  MaterialPageRoute(
                    builder: (context) => const StudentRegisterScreen(),
                  ),
                );
              },
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () async {
              final newUrl = controller.text.trim();
              if (newUrl.isNotEmpty) {
                await AppSettings.updateServerUrl(newUrl);
                _loadProfile();
              }
              if (ctx.mounted) Navigator.of(ctx).pop();
            },
            child: const Text('Save Server URL'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final hasActiveSubject = _currentClass != null && _currentClass!['subject'] != null;
    final subjectName = hasActiveSubject ? _currentClass!['subject'] : 'No Class Scheduled';
    final teacherEmail = hasActiveSubject ? _currentClass!['teacher_email'] ?? '' : '';
    final isWindowOpen = _windowStatus != null && _windowStatus!['is_open'] == true;
    final windowMessage = _windowStatus != null ? _windowStatus!['message'] ?? '' : '';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Smart Attendance'),
        centerTitle: true,
        backgroundColor: const Color(0xFF16213E),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh Status',
            onPressed: () {
              _fetchLiveTimetable();
              _startManualBeaconScan();
            },
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Settings',
            onPressed: _showSettingsDialog,
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async {
            await _fetchLiveTimetable();
            await _startManualBeaconScan();
          },
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // 1. Student Profile Header Card
                Card(
                  elevation: 2,
                  color: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        CircleAvatar(
                          radius: 26,
                          backgroundColor: const Color(0xFF0F3460),
                          child: Text(
                            _studentName.isNotEmpty
                                ? _studentName.substring(0, 1).toUpperCase()
                                : '?',
                            style: const TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                _studentName.isNotEmpty ? _studentName : 'Student Profile',
                                style: theme.textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                'Roll No: ${_studentRoll.isNotEmpty ? _studentRoll : "Not Registered"}',
                                style: TextStyle(
                                  color: Colors.grey.shade700,
                                  fontWeight: FontWeight.w600,
                                  fontSize: 13,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(
                                  color: Colors.green.shade50,
                                  borderRadius: BorderRadius.circular(6),
                                  border: Border.all(color: Colors.green.shade300),
                                ),
                                child: const Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(Icons.verified, size: 12, color: Colors.green),
                                    SizedBox(width: 4),
                                    Text(
                                      'Biometrics Locked & Secure',
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.bold,
                                        color: Colors.green,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 14),

                // 2. Live Timetable & Active Class Card
                Card(
                  elevation: 2,
                  color: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                    side: BorderSide(
                      color: isWindowOpen ? Colors.green.shade400 : Colors.grey.shade300,
                      width: isWindowOpen ? 2 : 1,
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Row(
                              children: [
                                Icon(Icons.school, color: isWindowOpen ? Colors.green : const Color(0xFF0F3460), size: 22),
                                const SizedBox(width: 8),
                                const Text(
                                  'Current Scheduled Class',
                                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                                ),
                              ],
                            ),
                            if (_isLoadingTimetable)
                              const SizedBox(
                                width: 14,
                                height: 14,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            else if (_serverDay.isNotEmpty)
                              Text(
                                '$_serverDay ${_serverTime.length >= 5 ? _serverTime.substring(0, 5) : ""}',
                                style: TextStyle(color: Colors.grey.shade600, fontSize: 12, fontWeight: FontWeight.bold),
                              ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        Text(
                          subjectName,
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: hasActiveSubject ? Colors.black87 : Colors.grey.shade600,
                          ),
                        ),
                        if (teacherEmail.isNotEmpty) ...[
                          const SizedBox(height: 2),
                          Text(
                            'Teacher: $teacherEmail',
                            style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                          ),
                        ],
                        const SizedBox(height: 12),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                          decoration: BoxDecoration(
                            color: isWindowOpen ? Colors.green.shade50 : (hasActiveSubject ? Colors.red.shade50 : Colors.grey.shade100),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: isWindowOpen ? Colors.green.shade300 : (hasActiveSubject ? Colors.red.shade300 : Colors.grey.shade300),
                            ),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                isWindowOpen ? Icons.check_circle : (hasActiveSubject ? Icons.access_time_filled : Icons.info),
                                color: isWindowOpen ? Colors.green : (hasActiveSubject ? Colors.red : Colors.grey.shade700),
                                size: 18,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  isWindowOpen
                                      ? 'Window OPEN — You can mark attendance now!'
                                      : (windowMessage.isNotEmpty ? windowMessage : 'No active attendance window.'),
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: isWindowOpen ? Colors.green.shade800 : (hasActiveSubject ? Colors.red.shade800 : Colors.grey.shade700),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 14),

                // 3. ESP32 Classroom Beacon Live Radar Card
                Card(
                  elevation: 2,
                  color: const Color(0xFF16213E),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Row(
                              children: [
                                Icon(Icons.bluetooth_searching, color: Color(0xFFE94560), size: 24),
                                SizedBox(width: 8),
                                Text(
                                  'ESP32 Classroom Beacon',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 15,
                                  ),
                                ),
                              ],
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                              decoration: BoxDecoration(
                                color: _isBeaconDetected ? Colors.green.withValues(alpha: 0.2) : Colors.red.withValues(alpha: 0.2),
                                borderRadius: BorderRadius.circular(6),
                                border: Border.all(
                                  color: _isBeaconDetected ? Colors.greenAccent : Colors.redAccent,
                                ),
                              ),
                              child: Text(
                                _isBeaconDetected ? 'IN CLASS' : 'NOT DETECTED',
                                style: TextStyle(
                                  color: _isBeaconDetected ? Colors.greenAccent : Colors.redAccent,
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        Text(
                          _bleStatusMessage,
                          style: TextStyle(
                            color: Colors.grey.shade300,
                            fontSize: 12,
                          ),
                        ),
                        if (_isBeaconDetected && _beaconRssi != null) ...[
                          const SizedBox(height: 6),
                          Row(
                            children: [
                              const Icon(Icons.signal_cellular_alt, color: Colors.greenAccent, size: 16),
                              const SizedBox(width: 6),
                              Text(
                                'RSSI: $_beaconRssi dBm  •  $_beaconName',
                                style: const TextStyle(color: Colors.greenAccent, fontSize: 12, fontWeight: FontWeight.bold),
                              ),
                            ],
                          ),
                        ],
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton.icon(
                                onPressed: _isManualScanning ? null : _startManualBeaconScan,
                                style: OutlinedButton.styleFrom(
                                  foregroundColor: Colors.white,
                                  side: const BorderSide(color: Colors.white54),
                                ),
                                icon: _isManualScanning
                                    ? const SizedBox(
                                        width: 14,
                                        height: 14,
                                        child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                                      )
                                    : const Icon(Icons.radar, size: 18),
                                label: Text(_isManualScanning ? 'Scanning...' : 'Scan for ESP32 Beacon'),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 20),

                // 4. Primary Action: Face Scan Button
                SizedBox(
                  height: 54,
                  child: FilledButton.icon(
                    onPressed: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => const FaceScanScreen(),
                        ),
                      );
                    },
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFFE94560),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    icon: const Icon(Icons.camera_alt, size: 24),
                    label: const Text(
                      'Mark Attendance (Face Scan)',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
                // 5. Analytics & 75% Tracker Button
                SizedBox(
                  height: 50,
                  child: OutlinedButton.icon(
                    onPressed: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => StudentAnalyticsScreen(
                            serverUrl: _serverUrl,
                            rollNo: _studentRoll,
                            studentName: _studentName,
                          ),
                        ),
                      );
                    },
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFF0F3460),
                      side: const BorderSide(color: Color(0xFF0F3460), width: 1.5),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    icon: const Icon(Icons.analytics_outlined, size: 22),
                    label: const Text(
                      'My Attendance & 75% Shortage Tracker',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
                const SizedBox(height: 12),

                // Simulation helper button
                OutlinedButton.icon(
                  onPressed: () async {
                    await showClassroomNotification();
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Simulated classroom notification triggered! Tap it to open Face Scan.'),
                          duration: Duration(seconds: 3),
                        ),
                      );
                    }
                  },
                  icon: const Icon(Icons.notifications_active, size: 18),
                  label: const Text('Simulate Classroom Entry Notification', style: TextStyle(fontSize: 12)),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Face Scan Screen (opened on notification tap or button)
// ─────────────────────────────────────────────────────────────────────────────

class FaceScanScreen extends StatefulWidget {
  const FaceScanScreen({super.key});

  @override
  State<FaceScanScreen> createState() => _FaceScanScreenState();
}

class _FaceScanScreenState extends State<FaceScanScreen> {
  CameraController? _cameraController;
  bool _isCameraReady = false;
  bool _isProcessing = false;
  String _statusMessage = 'Align your face inside the frame and tap Capture.';
  Color _statusColor = Colors.black87;
  String _serverUrl = kDefaultApiBaseUrl;
  String _studentName = '';
  String _studentRoll = '';

  @override
  void initState() {
    super.initState();
    _loadSettings();
    _initializeCamera();
  }

  Future<void> _loadSettings() async {
    final server = await AppSettings.getServerUrl();
    final name = await AppSettings.getStudentName();
    final roll = await AppSettings.getStudentRoll();
    if (mounted) {
      setState(() {
        _serverUrl = server;
        _studentName = name;
        _studentRoll = roll;
      });
    }
  }

  Future<void> _initializeCamera() async {
    if (_cameras.isEmpty) {
      try {
        _cameras = await availableCameras();
      } catch (e) {
        _setStatus('No cameras available on this device.', Colors.red);
        return;
      }
    }

    CameraDescription? frontCamera;
    for (final cam in _cameras) {
      if (cam.lensDirection == CameraLensDirection.front) {
        frontCamera = cam;
        break;
      }
    }
    frontCamera ??= _cameras.isNotEmpty ? _cameras.first : null;

    if (frontCamera == null) {
      _setStatus('No front camera found.', Colors.red);
      return;
    }

    final controller = CameraController(
      frontCamera,
      ResolutionPreset.medium,
      enableAudio: false,
    );

    try {
      await controller.initialize();
      if (!mounted) return;
      setState(() {
        _cameraController = controller;
        _isCameraReady = true;
      });
    } catch (e) {
      _setStatus('Camera error: $e', Colors.red);
    }
  }

  void _setStatus(String message, Color color) {
    if (!mounted) return;
    setState(() {
      _statusMessage = message;
      _statusColor = color;
    });
  }

  Future<void> _captureAndVerify() async {
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      _setStatus('Camera is not ready.', Colors.red);
      return;
    }

    setState(() => _isProcessing = true);
    _setStatus('Capturing photo…', Colors.indigo);

    try {
      final XFile image = await _cameraController!.takePicture();
      final dir = await getTemporaryDirectory();
      final path =
          '${dir.path}/face_scan_${DateTime.now().millisecondsSinceEpoch}.jpg';
      await File(image.path).copy(path);

      _setStatus('Checking time window & verifying face…', Colors.indigo);

      final deviceId = await AppSettings.getDeviceId();
      final uri = Uri.parse('$_serverUrl/verify');
      final request = http.MultipartRequest('POST', uri)
        ..files.add(await http.MultipartFile.fromPath('photo', path));
      if (_studentRoll.isNotEmpty) {
        request.fields['roll_no'] = _studentRoll;
      }
      request.fields['device_id'] = deviceId;

      final streamed = await request.send().timeout(
            const Duration(seconds: 15),
          );
      final response = await http.Response.fromStream(streamed);
      final Map<String, dynamic> data =
          jsonDecode(response.body) as Map<String, dynamic>;

      debugPrint('[VERIFY API] Status ${response.statusCode}: ${response.body}');

      if (response.statusCode == 200) {
        final status = data['status'] ?? '';
        final name = data['name'] ?? '';
        final rollNo = data['roll_no'] ?? '';
        final time = data['time'] ?? '';
        if (status == 'already_marked') {
          _setStatus(
            'ℹ️ Already Marked Today!\n\nStudent: $name\nRoll No: $rollNo',
            Colors.indigo.shade800,
          );
        } else {
          _setStatus(
            '✅ Attendance Marked Successfully!\n\nStudent: $name\nRoll No: $rollNo\nTime: $time',
            Colors.green.shade800,
          );
        }
      } else if (response.statusCode == 403) {
        final detail = data['detail'] ?? 'Time limit exceeded.';
        _setStatus('⏰ Rejection (Strict Window):\n$detail', Colors.red.shade800);
      } else if (response.statusCode == 404) {
        final detail = data['detail'] ?? 'Face not recognized.';
        _setStatus('🚫 Face Not Matched:\n$detail', Colors.red.shade800);
      } else {
        final detail = data['detail'] ?? 'Verification failed (${response.statusCode})';
        _setStatus('❌ $detail', Colors.red.shade800);
      }

      try {
        await File(path).delete();
      } catch (_) {}
    } on SocketException {
      _setStatus(
        '❌ Connection error:\nCannot reach backend at $_serverUrl',
        Colors.red.shade800,
      );
    } on TimeoutException {
      _setStatus('❌ Request timed out. Try again.', Colors.red.shade800);
    } catch (e) {
      _setStatus('❌ Error: $e', Colors.red.shade800);
    } finally {
      if (mounted) {
        setState(() => _isProcessing = false);
      }
    }
  }

  @override
  void dispose() {
    _cameraController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Face Scan Attendance'),
        centerTitle: true,
        backgroundColor: const Color(0xFF16213E),
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: Column(
          children: [
            if (_studentName.isNotEmpty)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                color: const Color(0xFF0F3460).withValues(alpha: 0.15),
                child: Text(
                  'Marking for: $_studentName (${_studentRoll.isNotEmpty ? _studentRoll : ""})',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF0F3460),
                  ),
                ),
              ),

            const SizedBox(height: 10),

            // Camera Preview with Oval Frame
            Expanded(
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 20),
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(20),
                ),
                clipBehavior: Clip.antiAlias,
                child: _isCameraReady && _cameraController != null
                    ? Stack(
                        alignment: Alignment.center,
                        children: [
                          CameraPreview(_cameraController!),
                          Container(
                            width: 240,
                            height: 320,
                            decoration: BoxDecoration(
                              shape: BoxShape.rectangle,
                              borderRadius: BorderRadius.circular(120),
                              border: Border.all(
                                color: Colors.white.withAlpha(200),
                                width: 3,
                              ),
                            ),
                          ),
                        ],
                      )
                    : const Center(
                        child: CircularProgressIndicator(color: Colors.white),
                      ),
              ),
            ),

            const SizedBox(height: 16),

            // Status message card
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.grey.shade300),
                ),
                child: Text(
                  _statusMessage,
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: _statusColor,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),

            const SizedBox(height: 20),

            // Action Button
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              child: SizedBox(
                width: double.infinity,
                height: 56,
                child: FilledButton.icon(
                  onPressed: _isProcessing ? null : _captureAndVerify,
                  icon: _isProcessing
                      ? const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.5,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.camera, size: 28),
                  label: Text(
                    _isProcessing ? 'Verifying…' : 'Capture & Verify',
                    style: const TextStyle(fontSize: 16),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Student Attendance Analytics & 75% Tracker Screen
// ─────────────────────────────────────────────────────────────────────────────

class StudentAnalyticsScreen extends StatefulWidget {
  final String serverUrl;
  final String rollNo;
  final String studentName;

  const StudentAnalyticsScreen({
    super.key,
    required this.serverUrl,
    required this.rollNo,
    required this.studentName,
  });

  @override
  State<StudentAnalyticsScreen> createState() => _StudentAnalyticsScreenState();
}

class _StudentAnalyticsScreenState extends State<StudentAnalyticsScreen> {
  bool _isLoading = true;
  String? _errorMessage;
  Map<String, dynamic>? _analyticsData;

  @override
  void initState() {
    super.initState();
    _loadAnalytics();
  }

  Future<void> _loadAnalytics() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final uri = Uri.parse('${widget.serverUrl}/students/${widget.rollNo}/analytics');
      final res = await http.get(uri).timeout(const Duration(seconds: 12));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        if (mounted) {
          setState(() {
            _analyticsData = data;
            _isLoading = false;
          });
        }
      } else {
        final err = jsonDecode(res.body)['detail'] ?? 'Failed to load analytics (${res.statusCode})';
        if (mounted) {
          setState(() {
            _errorMessage = err.toString();
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Connection error: $e';
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final overallPct = (_analyticsData?['overall_percentage'] as num?)?.toDouble() ?? 0.0;
    final isShortage = _analyticsData?['is_shortage'] ?? false;
    final totalAttended = _analyticsData?['total_attended'] ?? 0;
    final totalHeld = _analyticsData?['total_held'] ?? 0;
    final subjects = (_analyticsData?['subjects'] as List<dynamic>?) ?? [];
    final records = (_analyticsData?['records'] as List<dynamic>?) ?? [];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Attendance Analytics'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _isLoading ? null : _loadAnalytics,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.error_outline, color: Colors.red, size: 48),
                        const SizedBox(height: 12),
                        Text(
                          _errorMessage!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: Colors.red, fontSize: 14),
                        ),
                        const SizedBox(height: 16),
                        FilledButton.tonal(
                          onPressed: _loadAnalytics,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadAnalytics,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      // Header Profile info
                      Row(
                        children: [
                          CircleAvatar(
                            radius: 22,
                            backgroundColor: const Color(0xFF0F3460),
                            child: Text(
                              widget.studentName.isNotEmpty ? widget.studentName[0].toUpperCase() : 'S',
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  widget.studentName,
                                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                                ),
                                Text(
                                  'Roll No: ${widget.rollNo}',
                                  style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // 1. Overall Percentage Gauge Card
                      Card(
                        elevation: 2,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                          side: BorderSide(
                            color: isShortage ? Colors.red.shade300 : Colors.green.shade300,
                            width: 1.5,
                          ),
                        ),
                        color: isShortage ? Colors.red.shade50 : Colors.green.shade50,
                        child: Padding(
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      const Text(
                                        'Overall Attendance',
                                        style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Colors.black87),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        '$overallPct%',
                                        style: TextStyle(
                                          fontSize: 36,
                                          fontWeight: FontWeight.bold,
                                          color: isShortage ? Colors.red.shade800 : Colors.green.shade800,
                                        ),
                                      ),
                                    ],
                                  ),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                                    decoration: BoxDecoration(
                                      color: isShortage ? Colors.red : Colors.green,
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      isShortage ? 'SHORTAGE ALERT' : 'ELIGIBLE (>=75%)',
                                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 11),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 12),
                              ClipRRect(
                                borderRadius: BorderRadius.circular(8),
                                child: LinearProgressIndicator(
                                  value: (overallPct / 100).clamp(0.0, 1.0),
                                  minHeight: 10,
                                  backgroundColor: Colors.white,
                                  valueColor: AlwaysStoppedAnimation<Color>(
                                    isShortage ? Colors.red : Colors.green,
                                  ),
                                ),
                              ),
                              const SizedBox(height: 12),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    'Classes Attended: $totalAttended / $totalHeld',
                                    style: TextStyle(fontSize: 12, color: Colors.grey.shade800, fontWeight: FontWeight.w600),
                                  ),
                                  Text(
                                    'Target: >= 75%',
                                    style: TextStyle(fontSize: 12, color: Colors.grey.shade800, fontWeight: FontWeight.bold),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 20),

                      // 2. Subject Breakdown Section
                      Text(
                        'Subject-Wise Performance',
                        style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 10),

                      if (subjects.isEmpty)
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: Colors.grey.shade100,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Center(
                            child: Text('No subject attendance data available yet.'),
                          ),
                        )
                      else
                        ...subjects.map((subj) {
                          final sName = subj['subject'] ?? 'Unknown';
                          final sAtt = subj['attended'] ?? 0;
                          final sHeld = subj['total_held'] ?? 1;
                          final sPct = (subj['percentage'] as num?)?.toDouble() ?? 0.0;
                          final sShortage = subj['shortage'] ?? false;

                          return Card(
                            margin: const EdgeInsets.only(bottom: 10),
                            elevation: 1,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                              side: BorderSide(color: sShortage ? Colors.red.shade200 : Colors.grey.shade300),
                            ),
                            child: Padding(
                              padding: const EdgeInsets.all(14),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Expanded(
                                        child: Text(
                                          sName,
                                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                                        ),
                                      ),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                        decoration: BoxDecoration(
                                          color: sShortage ? Colors.red.shade100 : Colors.green.shade100,
                                          borderRadius: BorderRadius.circular(6),
                                        ),
                                        child: Text(
                                          '$sPct%',
                                          style: TextStyle(
                                            fontWeight: FontWeight.bold,
                                            fontSize: 12,
                                            color: sShortage ? Colors.red.shade800 : Colors.green.shade800,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 8),
                                  ClipRRect(
                                    borderRadius: BorderRadius.circular(4),
                                    child: LinearProgressIndicator(
                                      value: (sPct / 100).clamp(0.0, 1.0),
                                      minHeight: 6,
                                      backgroundColor: Colors.grey.shade200,
                                      valueColor: AlwaysStoppedAnimation<Color>(
                                        sShortage ? Colors.red : Colors.green,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(height: 6),
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text(
                                        'Attended: $sAtt / $sHeld classes',
                                        style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                                      ),
                                      if (sShortage)
                                        const Text(
                                          '⚠️ Below 75%',
                                          style: TextStyle(fontSize: 11, color: Colors.red, fontWeight: FontWeight.bold),
                                        ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          );
                        }),
                      const SizedBox(height: 20),

                      // 3. Attendance History Logs
                      Text(
                        'Recent Attendance Log',
                        style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 10),

                      if (records.isEmpty)
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: Colors.grey.shade100,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Center(
                            child: Text('No attendance marked yet.'),
                          ),
                        )
                      else
                        ...records.take(15).map((r) {
                          return Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(color: Colors.grey.shade200),
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Row(
                                  children: [
                                    const Icon(Icons.check_circle, color: Colors.green, size: 20),
                                    const SizedBox(width: 10),
                                    Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          r['subject'] ?? 'Class',
                                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                                        ),
                                        Text(
                                          '${r['date']} • ${r['time']}',
                                          style: TextStyle(color: Colors.grey.shade600, fontSize: 11),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: Colors.green.shade50,
                                    borderRadius: BorderRadius.circular(6),
                                    border: Border.all(color: Colors.green.shade200),
                                  ),
                                  child: const Text(
                                    'Present',
                                    style: TextStyle(color: Colors.green, fontSize: 11, fontWeight: FontWeight.bold),
                                  ),
                                ),
                              ],
                            ),
                          );
                        }),
                    ],
                  ),
                ),
    );
  }
}
