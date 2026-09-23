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
import 'register_screen.dart';
import 'attendance_screen.dart';
import 'face_scan_screen.dart';
import 'analytics_screen.dart';
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
  String _studentBranch = '';
  String _studentSection = '';
  String _studentYear = '';

  @override
  void initState() {
    super.initState();
    _loadSettings();
    _initializeCamera();
  }

  Future<void> _initializeCamera() async {
    if (globalCameras.isEmpty) {
      try {
        globalCameras = await availableCameras();
      } catch (e) {
        _setStatus('No cameras available on this device.', Colors.red);
        return;
      }
    }

    CameraDescription? frontCamera;
    for (final cam in globalCameras) {
      if (cam.lensDirection == CameraLensDirection.front) {
        frontCamera = cam;
        break;
      }
    }
    frontCamera ??= globalCameras.isNotEmpty ? globalCameras.first : null;

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

  Future<void> _loadSettings() async {
    final server = await AppSettings.getServerUrl();
    final name = await AppSettings.getStudentName();
    final roll = await AppSettings.getStudentRoll();
    final branch = await AppSettings.getStudentBranch();
    final section = await AppSettings.getStudentSection();
    final year = await AppSettings.getStudentYear();
    if (mounted) {
      setState(() {
        _serverUrl = server;
        _studentName = name;
        _studentRoll = roll;
        _studentBranch = branch;
        _studentSection = section;
        _studentYear = year;
      });
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
        ..headers.addAll(kDefaultHttpHeaders)
        ..files.add(await http.MultipartFile.fromPath('photo', path));
      if (_studentRoll.isNotEmpty) {
        request.fields['roll_no'] = _studentRoll;
      }
      request.fields['device_id'] = deviceId;

      final streamed = await request.send().timeout(
            const Duration(seconds: 60),
          );
      final response = await http.Response.fromStream(streamed);

      if (response.statusCode == 503 || response.body.contains('503') || response.body.contains('Tunnel Unavailable')) {
        _setStatus(
          '❌ Cloud Tunnel is Offline (503).\nPlease ensure START_SERVER.bat is running on your laptop.',
          Colors.red.shade800,
        );
        return;
      }

      Map<String, dynamic> data = {};
      try {
        data = jsonDecode(response.body) as Map<String, dynamic>;
      } catch (_) {
        _setStatus(
          '❌ Server error (${response.statusCode}):\n${response.body.length > 120 ? response.body.substring(0, 120) : response.body}',
          Colors.red.shade800,
        );
        return;
      }

      debugPrint('[VERIFY API] Status ${response.statusCode}: ${response.body}');

      if (response.statusCode == 200) {
        final status = data['status'] ?? '';
        final name = data['name'] ?? '';
        final rollNo = data['roll_no'] ?? '';
        final time = data['time'] ?? '';
        final confidence = data['confidence'] ?? 0;
        final confStr = confidence > 0 ? '\nMatch Confidence: $confidence%' : '';
        if (status == 'already_marked') {
          _setStatus(
            'ℹ️ Already Marked Today!\n\nStudent: $name\nRoll No: $rollNo$confStr',
            Colors.indigo.shade800,
          );
        } else {
          _setStatus(
            '✅ Attendance Marked Successfully!\n\nStudent: $name\nRoll No: $rollNo\nTime: $time$confStr',
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
                child: Column(
                  children: [
                    Text(
                      'Marking for: $_studentName (${_studentRoll.isNotEmpty ? _studentRoll : ""})',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                        color: Color(0xFF0F3460),
                      ),
                    ),
                    if (_studentBranch.isNotEmpty || _studentSection.isNotEmpty || _studentYear.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        '${AppSettings.getYearLabel(_studentYear.isNotEmpty ? _studentYear : _studentSection)} • Section ${_studentSection.isNotEmpty ? _studentSection : "N/A"} • ${kBranches[_studentBranch] ?? _studentBranch}',
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFFE94560),
                        ),
                      ),
                    ],
                  ],
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
                    _isProcessing ? 'Processing…' : 'Capture & Verify',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
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

