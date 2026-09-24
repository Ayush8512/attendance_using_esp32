import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui';
import 'package:camera/camera.dart';
import 'package:google_mlkit_face_detection/google_mlkit_face_detection.dart';
import 'package:flutter/foundation.dart';
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
  
  // Liveness (Blink Detection) State
  FaceDetector? _faceDetector;
  bool _isDetecting = false;
  int _blinkState = 0; // 0: Start, 1: Eyes Open, 2: Eyes Closed (Blinking), 3: Blink Finished (Capture)

  String _statusMessage = 'Looking for face... Please BLINK to capture.';
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
    _faceDetector = FaceDetector(
      options: FaceDetectorOptions(
        enableClassification: true, // Needed for eye open probability
        enableTracking: true,
        performanceMode: FaceDetectorMode.fast,
      ),
    );
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
      imageFormatGroup: Platform.isAndroid ? ImageFormatGroup.nv21 : ImageFormatGroup.bgra8888,
    );

    try {
      await controller.initialize();
      if (!mounted) return;
      
      setState(() {
        _cameraController = controller;
        _isCameraReady = true;
      });

      // Start Image Stream for Blink Detection
      controller.startImageStream(_processCameraImage);

    } catch (e) {
      _setStatus('Camera error: $e', Colors.red);
    }
  }

  void _processCameraImage(CameraImage image) async {
    if (_isProcessing || _isDetecting || _blinkState == 3 || !mounted) return;
    _isDetecting = true;

    try {
      final inputImage = _inputImageFromCameraImage(image);
      if (inputImage == null) {
        _isDetecting = false;
        return;
      }

      final faces = await _faceDetector!.processImage(inputImage);
      
      if (faces.isEmpty) {
        if (_blinkState != 0) {
          _blinkState = 0; // reset if face lost
          _setStatus('Face lost. Align your face.', Colors.orange.shade800);
        }
      } else {
        final face = faces.first;
        final leftEyeOpen = face.leftEyeOpenProbability ?? 1.0;
        final rightEyeOpen = face.rightEyeOpenProbability ?? 1.0;

        if (_blinkState == 0 && leftEyeOpen > 0.7 && rightEyeOpen > 0.7) {
          _blinkState = 1; // Eyes are open, waiting for blink
          _setStatus('Face detected. Please BLINK to capture.', Colors.indigo);
        } 
        else if (_blinkState == 1 && leftEyeOpen < 0.2 && rightEyeOpen < 0.2) {
          _blinkState = 2; // Eyes closed (Blinking)
          _setStatus('Blink detected! Capturing...', Colors.green.shade800);
        } 
        else if (_blinkState == 2 && leftEyeOpen > 0.7 && rightEyeOpen > 0.7) {
          _blinkState = 3; // Eyes opened again. Trigger Capture!
          // Stop stream and capture
          await _cameraController?.stopImageStream();
          _captureAndVerify();
        }
      }
    } catch (e) {
      debugPrint("ML Kit Error: $e");
    }

    _isDetecting = false;
  }

  InputImage? _inputImageFromCameraImage(CameraImage image) {
    final camera = _cameraController;
    if (camera == null) return null;

    final rotation = InputImageRotationValue.fromRawValue(camera.description.sensorOrientation);
    if (rotation == null) return null;

    final format = InputImageFormatValue.fromRawValue(image.format.raw);
    if (format == null) return null;

    if (image.planes.isEmpty) return null;

    final WriteBuffer allBytes = WriteBuffer();
    for (final Plane plane in image.planes) {
      allBytes.putUint8List(plane.bytes);
    }
    final bytes = allBytes.done().buffer.asUint8List();

    final Size imageSize = Size(image.width.toDouble(), image.height.toDouble());

    final metadata = InputImageMetadata(
      size: imageSize,
      rotation: rotation,
      format: format,
      bytesPerRow: image.planes[0].bytesPerRow,
    );

    return InputImage.fromBytes(bytes: bytes, metadata: metadata);
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
    _setStatus('Liveness Confirmed! Uploading to Server...', Colors.indigo);

    try {
      final XFile image = await _cameraController!.takePicture();
      final dir = await getTemporaryDirectory();
      final path = '${dir.path}/face_scan_${DateTime.now().millisecondsSinceEpoch}.jpg';
      await File(image.path).copy(path);

      _setStatus('Checking time window & verifying face...', Colors.indigo);

      final deviceId = await AppSettings.getDeviceId();
      final uri = Uri.parse('$_serverUrl/verify');
      final request = http.MultipartRequest('POST', uri)
        ..headers.addAll(kDefaultHttpHeaders)
        ..files.add(await http.MultipartFile.fromPath('photo', path));
      if (_studentRoll.isNotEmpty) {
        request.fields['roll_no'] = _studentRoll;
      }
      request.fields['device_id'] = deviceId;

      final streamed = await request.send().timeout(const Duration(seconds: 60));
      final response = await http.Response.fromStream(streamed);

      if (response.statusCode == 503 || response.body.contains('503') || response.body.contains('Tunnel Unavailable')) {
        _setStatus('❌ Cloud Tunnel is Offline (503).\nPlease ensure START_SERVER.bat is running on your laptop.', Colors.red.shade800);
        return;
      }

      Map<String, dynamic> data = {};
      try {
        data = jsonDecode(response.body) as Map<String, dynamic>;
      } catch (_) {
        _setStatus('❌ Server error (${response.statusCode})', Colors.red.shade800);
        return;
      }

      if (response.statusCode == 200) {
        final status = data['status'] ?? '';
        final name = data['name'] ?? '';
        final rollNo = data['roll_no'] ?? '';
        final time = data['time'] ?? '';
        final confidence = data['confidence'] ?? 0;
        final confStr = confidence > 0 ? '\nMatch Confidence: $confidence%' : '';
        if (status == 'already_marked') {
          _setStatus('✅ Already Marked Today!\n\nStudent: $name\nRoll No: $rollNo$confStr', Colors.indigo.shade800);
        } else {
          _setStatus('✅ Attendance Marked Successfully!\n\nStudent: $name\nRoll No: $rollNo\nTime: $time$confStr', Colors.green.shade800);
        }
      } else if (response.statusCode == 403) {
        final detail = data['detail'] ?? 'Time limit exceeded.';
        _setStatus('🚫 Rejection (Strict Window):\n$detail', Colors.red.shade800);
      } else if (response.statusCode == 404) {
        final detail = data['detail'] ?? 'Face not recognized.';
        _setStatus('❌ Face Not Matched:\n$detail', Colors.red.shade800);
      } else {
        final detail = data['detail'] ?? 'Verification failed';
        _setStatus('❌ $detail', Colors.red.shade800);
      }

      try {
        await File(path).delete();
      } catch (_) {}
    } catch (e) {
      _setStatus('Network or connection error.', Colors.red.shade800);
    } finally {
      if (mounted) {
        setState(() => _isProcessing = false);
        // Do not restart stream automatically to avoid infinite loops, let them tap retry if failed
      }
    }
  }

  @override
  void dispose() {
    _cameraController?.stopImageStream();
    _cameraController?.dispose();
    _faceDetector?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: const Text('Face Scan Attendance'),
        backgroundColor: Colors.indigo.shade900,
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            children: [
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
                color: Colors.indigo.shade50,
                child: Column(
                  children: [
                    Text(
                      'Marking for: ${_studentName.toUpperCase()} ($_studentRoll)',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: Colors.indigo.shade900,
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
              const SizedBox(height: 20),
              Center(
                child: Container(
                  width: 280,
                  height: 360,
                  decoration: BoxDecoration(
                    color: Colors.grey.shade300,
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
                                border: Border.all(color: Colors.white70, width: 3),
                                borderRadius: BorderRadius.circular(120),
                              ),
                            ),
                          ],
                        )
                      : const Center(
                          child: CircularProgressIndicator(color: Colors.indigo),
                        ),
                ),
              ),
              const SizedBox(height: 20),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: _statusColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: _statusColor.withOpacity(0.3)),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        _isProcessing
                            ? Icons.hourglass_top
                            : (_blinkState == 3 ? Icons.check_circle : Icons.face_retouching_natural),
                        color: _statusColor,
                        size: 28,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          _statusMessage,
                          style: TextStyle(
                            fontSize: 15,
                            color: _statusColor,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: SizedBox(
                  width: double.infinity,
                  height: 56,
                  child: FilledButton.icon(
                    onPressed: _isProcessing ? null : () {
                      // Manual override just in case blink detection fails
                      if (_blinkState != 3) {
                         _cameraController?.stopImageStream();
                        _captureAndVerify();
                      }
                    },
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
                      _isProcessing ? 'Uploading...' : 'Manual Override Capture',
                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
