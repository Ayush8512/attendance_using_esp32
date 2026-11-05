import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import '../utils/constants.dart';

class FaceScanScreen extends StatefulWidget {
  const FaceScanScreen({super.key});

  @override
  State<FaceScanScreen> createState() => _FaceScanScreenState();
}

class _FaceScanScreenState extends State<FaceScanScreen> {
  CameraController? _cameraController;
  bool _isCameraReady = false;
  bool _isProcessing = false;
  bool _isSuccess = false;

  String _statusMessage = 'Align your face in the oval and tap "Mark Attendance".';
  Color _statusColor = const Color(0xFF0F3460);
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

  Future<void> _loadSettings() async {
    final server = await AppSettings.getServerUrl();
    final name = await AppSettings.getStudentName();
    final roll = await AppSettings.getStudentRoll();
    final branch = await AppSettings.getStudentBranch();
    final section = await AppSettings.getStudentSection();
    final year = await AppSettings.getStudentYear();
    if (mounted) {
      setState(() {
        _serverUrl = server.isNotEmpty ? server : kDefaultApiBaseUrl;
        _studentName = name;
        _studentRoll = roll;
        _studentBranch = branch;
        _studentSection = section;
        _studentYear = year;
      });
    }
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
      _setStatus('No front camera found on this device.', Colors.red);
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
    if (_isProcessing) return;
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      _setStatus('Camera is not ready yet. Please wait...', Colors.red);
      return;
    }

    setState(() {
      _isProcessing = true;
      _isSuccess = false;
    });
    _setStatus('Capturing photo and verifying face...', const Color(0xFF0F3460));

    String? tempFilePath;
    try {
      final XFile image = await _cameraController!.takePicture();
      final dir = await getTemporaryDirectory();
      tempFilePath = '${dir.path}/face_scan_${DateTime.now().millisecondsSinceEpoch}.jpg';
      await File(image.path).copy(tempFilePath);

      _setStatus('Verifying face with server & time window...', const Color(0xFF0F3460));

      final deviceId = await AppSettings.getDeviceId();
      final uri = Uri.parse('$_serverUrl/verify');
      final request = http.MultipartRequest('POST', uri)
        ..headers.addAll(kDefaultHttpHeaders)
        ..files.add(await http.MultipartFile.fromPath('photo', tempFilePath));

      if (_studentRoll.isNotEmpty) {
        request.fields['roll_no'] = _studentRoll;
      }
      if (deviceId.isNotEmpty) {
        request.fields['device_id'] = deviceId;
      }

      final streamed = await request.send().timeout(const Duration(seconds: 40));
      final response = await http.Response.fromStream(streamed);

      if (response.statusCode == 503 ||
          response.body.contains('503') ||
          response.body.contains('Tunnel Unavailable')) {
        _setStatus(
          '❌ Cloud Tunnel is Offline (503).\nPlease ensure the attendance server is running.',
          Colors.red.shade800,
        );
        return;
      }

      Map<String, dynamic> data = {};
      try {
        data = jsonDecode(response.body) as Map<String, dynamic>;
      } catch (_) {
        _setStatus('❌ Server response error (${response.statusCode})', Colors.red.shade800);
        return;
      }

      if (response.statusCode == 200) {
        final status = data['status'] ?? '';
        final name = data['name'] ?? _studentName;
        final rollNo = data['roll_no'] ?? _studentRoll;
        final time = data['time'] ?? '';
        final confidence = data['confidence'] ?? 0;
        final confStr = confidence > 0 ? '\nConfidence: $confidence%' : '';
        final subject = (data['subject'] ?? '').toString();
        final subjStr = subject.isNotEmpty ? '\nSubject: $subject' : '';

        setState(() => _isSuccess = true);

        if (status == 'already_marked') {
          _setStatus(
            '✅ Already Marked for this Class!\n\nStudent: $name\nRoll No: $rollNo$subjStr$confStr',
            Colors.indigo.shade800,
          );
        } else {
          _setStatus(
            '✅ Attendance Marked Successfully!\n\nStudent: $name\nRoll No: $rollNo$subjStr\nTime: $time$confStr',
            Colors.green.shade800,
          );
        }

        // Auto close after 2.5 seconds on success
        Future.delayed(const Duration(milliseconds: 2500), () {
          if (mounted) {
            Navigator.pop(context, true);
          }
        });
      } else if (response.statusCode == 403) {
        final detail = data['detail'] ?? 'Attendance window limit exceeded.';
        _setStatus('🚫 Time Window / Policy:\n$detail', Colors.red.shade800);
      } else if (response.statusCode == 404) {
        final detail = data['detail'] ?? 'Face not recognized.';
        _setStatus('❌ Face Not Matched:\n$detail', Colors.red.shade800);
      } else {
        final detail = data['detail'] ?? 'Verification failed (${response.statusCode})';
        _setStatus('❌ $detail', Colors.red.shade800);
      }
    } catch (e) {
      _setStatus('Network or connection error. Please retry.', Colors.red.shade800);
    } finally {
      if (tempFilePath != null) {
        try {
          await File(tempFilePath).delete();
        } catch (_) {}
      }
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
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: const Text('Face Scan Attendance'),
        backgroundColor: const Color(0xFF0F3460),
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            children: [
              // Header Card
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
                color: const Color(0xFF0F3460).withOpacity(0.06),
                child: Column(
                  children: [
                    Text(
                      'Marking for: ${_studentName.toUpperCase()} ($_studentRoll)',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF0F3460),
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '$_studentYear • Section $_studentSection • $_studentBranch',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: Colors.red.shade800,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Camera Preview Frame
              Center(
                child: Container(
                  width: 280,
                  height: 350,
                  decoration: BoxDecoration(
                    color: Colors.grey.shade200,
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.08),
                        blurRadius: 10,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: _isCameraReady && _cameraController != null
                      ? Stack(
                          alignment: Alignment.center,
                          children: [
                            CameraPreview(_cameraController!),
                            // Face Guide Oval
                            Container(
                              width: 220,
                              height: 300,
                              decoration: BoxDecoration(
                                border: Border.all(
                                  color: _isSuccess
                                      ? Colors.greenAccent
                                      : (_isProcessing ? Colors.amberAccent : Colors.white70),
                                  width: 3.5,
                                ),
                                borderRadius: BorderRadius.circular(110),
                              ),
                            ),
                          ],
                        )
                      : const Center(
                          child: CircularProgressIndicator(color: Color(0xFF0F3460)),
                        ),
                ),
              ),
              const SizedBox(height: 18),

              // Status Card
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: _statusColor.withOpacity(0.08),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: _statusColor.withOpacity(0.25)),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        _isSuccess
                            ? Icons.check_circle
                            : (_isProcessing ? Icons.hourglass_top : Icons.face),
                        color: _statusColor,
                        size: 26,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          _statusMessage,
                          style: TextStyle(
                            fontSize: 14,
                            color: _statusColor,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),

              // Primary Action: Capture & Mark Attendance Button
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: SizedBox(
                  width: double.infinity,
                  height: 56,
                  child: FilledButton.icon(
                    onPressed: _isProcessing
                        ? null
                        : (_isSuccess ? () => Navigator.pop(context, true) : _captureAndVerify),
                    style: FilledButton.styleFrom(
                      backgroundColor: _isSuccess ? Colors.green.shade700 : const Color(0xFFE94560),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    icon: _isProcessing
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(
                              strokeWidth: 2.5,
                              color: Colors.white,
                            ),
                          )
                        : Icon(_isSuccess ? Icons.check : Icons.camera_alt, size: 24),
                    label: Text(
                      _isProcessing
                          ? 'Verifying Face...'
                          : (_isSuccess ? 'Attendance Marked (Done)' : 'Mark Attendance (Capture Face)'),
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }
}
