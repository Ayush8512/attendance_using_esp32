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
class StudentRegisterScreen extends StatefulWidget {
  final bool isEditMode;
  const StudentRegisterScreen({super.key, this.isEditMode = false});

  @override
  State<StudentRegisterScreen> createState() => _StudentRegisterScreenState();
}

class _StudentRegisterScreenState extends State<StudentRegisterScreen> {
  CameraController? _cameraController;
  bool _isCameraReady = false;
  XFile? _capturedFacePhoto;
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _rollController = TextEditingController();
  final _serverController = TextEditingController(text: kDefaultApiBaseUrl);

  String? _selectedBranchCode;
  String? _selectedSection;
  String _classRollNo = '';
  bool _isSearchingRoster = false;
  Map<String, dynamic>? _matchedRosterStudent;
  Timer? _debounceTimer;


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

    final branch = await AppSettings.getStudentBranch();
    final section = await AppSettings.getStudentSection();
    final classRoll = await AppSettings.getStudentClassRoll();

    if (mounted) {
      setState(() {
        if (branch.isNotEmpty) _selectedBranchCode = branch;
        if (section.isNotEmpty) _selectedSection = section;
        _classRollNo = classRoll;
      });
    }

    if (widget.isEditMode) {
      _nameController.text = await AppSettings.getStudentName();
      _rollController.text = await AppSettings.getStudentRoll();
    }
  }

  Future<void> _initializeCamera() async {
    if (globalCameras.isEmpty) {
      try {
        globalCameras = await availableCameras();
      } catch (e) {
        debugPrint('[Camera] Init error: $e');
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
      debugPrint('[Camera] Capture error: $e');
    }
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    _nameController.dispose();
    _rollController.dispose();
    _serverController.dispose();
    _cameraController?.dispose();
    super.dispose();
  }


  void _onRollChanged(String value) {
    _debounceTimer?.cancel();
    final query = value.trim();
    if (query.length < 3) {
      setState(() => _matchedRosterStudent = null);
      return;
    }
    _debounceTimer = Timer(const Duration(milliseconds: 600), () {
      _lookupRosterStudent(query);
    });
  }

  Future<void> _lookupRosterStudent(String query) async {
    final serverUrl = _serverController.text.trim();
    if (serverUrl.isEmpty || query.trim().isEmpty) return;

    setState(() => _isSearchingRoster = true);
    try {
      final uri = Uri.parse('$serverUrl/roster/lookup/${Uri.encodeComponent(query.trim())}');
      final res = await http.get(uri, headers: kDefaultHttpHeaders).timeout(const Duration(seconds: 60));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        if (data['found'] == true && data['student'] != null) {
          final s = data['student'] as Map<String, dynamic>;
          if (mounted) {
            setState(() {
              _matchedRosterStudent = s;
              _nameController.text = s['name'] ?? _nameController.text;
              _selectedBranchCode = s['branch_code'] ?? _selectedBranchCode;
              _selectedSection = s['section'] ?? _selectedSection;
              _classRollNo = (s['class_roll_no'] ?? '').toString();
              if (s['aktu_roll_no'] != null && s['aktu_roll_no'].toString().isNotEmpty) {
                _rollController.text = s['aktu_roll_no'].toString();
              }
            });
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Verified Roster: ${s['name']} (${s['branch_name']} - ${s['section']})'),
                backgroundColor: Colors.green.shade700,
                duration: const Duration(seconds: 3),
              ),
            );
          }
        } else {
          if (mounted) setState(() => _matchedRosterStudent = null);
        }
      }
    } catch (e) {
      debugPrint('[RosterLookup] Error: $e');
    } finally {
      if (mounted) setState(() => _isSearchingRoster = false);
    }
  }

  void _openBrowseRosterModal() {
    final serverUrl = _serverController.text.trim();
    if (serverUrl.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter Server Base URL first.')),
      );
      return;
    }

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return _BrowseRosterSheet(
          serverUrl: serverUrl,
          initialBranch: _selectedBranchCode ?? 'A',
          initialSection: _selectedSection ?? 'A1',
          onSelectStudent: (s) {
            setState(() {
              _matchedRosterStudent = s;
              _nameController.text = s['name'] ?? '';
              _rollController.text = s['aktu_roll_no']?.toString().isNotEmpty == true
                  ? s['aktu_roll_no'].toString()
                  : (s['roll_no'] ?? '');
              _selectedBranchCode = s['branch_code'] ?? _selectedBranchCode;
              _selectedSection = s['section'] ?? _selectedSection;
              _classRollNo = (s['class_roll_no'] ?? '').toString();
            });
            Navigator.pop(ctx);
          },
        );
      },
    );
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
    final branchCode = _selectedBranchCode ?? '';
    final branchName = kBranches[branchCode] ?? '';
    final section = _selectedSection ?? '';

    try {
      final deviceId = await AppSettings.getDeviceId();
      final uri = Uri.parse('$serverUrl/register');
      final request = http.MultipartRequest('POST', uri)
        ..headers.addAll(kDefaultHttpHeaders)
        ..fields['name'] = name
        ..fields['roll_no'] = rollNo
        ..fields['device_id'] = deviceId;

      if (branchCode.isNotEmpty) {
        request.fields['branch_code'] = branchCode;
        request.fields['branch_name'] = branchName;
      }
      if (section.isNotEmpty) {
        request.fields['section'] = section;
      }
      if (_classRollNo.isNotEmpty) {
        request.fields['class_roll_no'] = _classRollNo;
      }

      request.files.add(
        await http.MultipartFile.fromPath(
          'photo',
          _capturedFacePhoto!.path,
        ),
      );

      final streamed = await request.send().timeout(const Duration(seconds: 60));
      final response = await http.Response.fromStream(streamed);
      if (response.statusCode == 503 || response.body.contains('503') || response.body.contains('Tunnel Unavailable')) {
        throw Exception('Cloud Tunnel / Server is currently offline (503). Please make sure START_SERVER.bat is running on your laptop.');
      }

      Map<String, dynamic> data = {};
      try {
        data = jsonDecode(response.body) as Map<String, dynamic>;
      } catch (_) {
        throw Exception('Server returned invalid response (${response.statusCode}).');
      }

      if (response.statusCode == 200 || response.statusCode == 201) {
        final yrLabel = AppSettings.getYearLabel(section);
        // Save locally in SharedPreferences
        await AppSettings.saveProfile(
          name: name,
          rollNo: rollNo,
          serverUrl: serverUrl,
          branch: branchCode,
          section: section,
          classRoll: _classRollNo,
        );

        if (!mounted) return;

        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (ctx) => AlertDialog(
            icon: const Icon(Icons.check_circle, color: Colors.green, size: 50),
            title: const Text('Registration Successful!'),
            content: Text(
              'Welcome $name!\n\n'
              '• Academic Year: $yrLabel\n'
              '• Branch: ${branchName.isNotEmpty ? branchName : "General"}\n'
              '• Section: ${section.isNotEmpty ? section : "N/A"}\n'
              '• Roll No: $rollNo\n\n'
              'Your profile and face biometrics are verified and saved.',
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
          content: Text('Connection timed out to $serverUrl.\nCheck if Laptop IP is correct and backend server is running.'),
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
      final deviceId = await AppSettings.getDeviceId();
      final uri = Uri.parse('$serverUrl/students/login');
      final response = await http.post(
        uri,
        headers: kDefaultHttpHeaders,
        body: {
          'roll_no': rollNo,
          'device_id': deviceId,
        },
      ).timeout(const Duration(seconds: 60));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final studentData = data['student'] as Map<String, dynamic>? ?? {};
        final studentName = studentData['name'] ?? 'Student';
        final studentRoll = studentData['roll_no'] ?? rollNo;
        final studentBranch = studentData['branch_code'] ?? '';
        final studentSection = studentData['section'] ?? '';
        final studentClassRoll = (studentData['class_roll_no'] ?? '').toString();
        final studentYear = (studentData['year'] ?? '').toString();
        final yrLabel = AppSettings.getYearLabel(studentYear.isNotEmpty ? studentYear : studentSection);

        await AppSettings.saveProfile(
          name: studentName,
          rollNo: studentRoll,
          serverUrl: serverUrl,
          branch: studentBranch,
          section: studentSection,
          classRoll: studentClassRoll,
          year: studentYear,
        );

        if (!mounted) return;
        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (ctx) => AlertDialog(
            icon: const Icon(Icons.verified_user, color: Colors.green, size: 50),
            title: const Text('Profile Restored!'),
            content: Text(
              'Welcome back, $studentName!\n\nYour profile ($yrLabel • Section: $studentSection • Roll: $studentRoll) is active on the server.',
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
        String errMsg = 'Roll No "$rollNo" is not registered or device mismatch.';
        try {
          final err = jsonDecode(response.body) as Map<String, dynamic>? ?? {};
          errMsg = err['detail'] ?? errMsg;
        } catch (_) {
          if (response.statusCode == 503 || response.body.contains('503') || response.body.contains('Tunnel Unavailable')) {
            errMsg = 'Cloud Tunnel is currently offline (503). Please make sure START_SERVER.bat is running on your laptop.';
          } else {
            errMsg = 'Server returned error (${response.statusCode})';
          }
        }
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(errMsg),
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

  List<String> _getAvailableSections() {
    if (_selectedBranchCode == null || _selectedBranchCode!.isEmpty) {
      return ['A1', 'A2', 'A3', 'A4', 'B1', 'B2', 'B3', 'B4', 'C1', 'C2', 'C3', 'C4', 'D1', 'D2', 'D3', 'D4', 'E1', 'E2', 'E3', 'E4', 'F1', 'F2', 'F3', 'F4', 'G1', 'G2', 'G3', 'G4'];
    }
    final code = _selectedBranchCode!;
    return ['$code 1', '$code 2', '$code 3', '$code 4']
        .map((s) => s.replaceAll(' ', ''))
        .toList();
  }



  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final availableSections = _getAvailableSections();

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
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Row(
                      children: [
                        const Icon(Icons.school_outlined, color: Color(0xFF0F3460), size: 28),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'IERT Prayagraj Student Onboarding',
                                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Color(0xFF0F3460)),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                'Select your Branch & Section or type your Roll No to auto-fill official details from the master college roster (1,706 students).',
                                style: TextStyle(fontSize: 12, color: Colors.grey.shade700, height: 1.3),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Quick Browse Roster Button
                OutlinedButton.icon(
                  onPressed: _openBrowseRosterModal,
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFF0F3460),
                    side: const BorderSide(color: Color(0xFF0F3460), width: 1.2),
                    padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: const Icon(Icons.list_alt, size: 20),
                  label: const Text(
                    '📋 Browse Section Roster (One-Tap Select)',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                  ),
                ),
                const SizedBox(height: 16),

                // Branch Dropdown
                DropdownButtonFormField<String>(
                  key: ValueKey('branch_$_selectedBranchCode'),
                  initialValue: _selectedBranchCode,
                  isExpanded: true,
                  decoration: InputDecoration(
                    labelText: 'Branch (A to G)',
                    prefixIcon: const Icon(Icons.apartment),
                    filled: true,
                    fillColor: Colors.white,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  hint: const Text('Select Branch'),
                  items: kBranches.entries.map((e) {
                    return DropdownMenuItem<String>(
                      value: e.key,
                      child: Text(
                        'Branch ${e.key} - ${e.value}',
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 13),
                      ),
                    );
                  }).toList(),
                  onChanged: (val) {
                    setState(() {
                      _selectedBranchCode = val;
                      final secList = _getAvailableSections();
                      if (_selectedSection == null || !secList.contains(_selectedSection)) {
                        _selectedSection = secList.first;
                      }
                    });
                  },
                ),
                const SizedBox(height: 14),

                // Section Dropdown
                DropdownButtonFormField<String>(
                  key: ValueKey('sec_${_selectedBranchCode}_$_selectedSection'),
                  initialValue: availableSections.contains(_selectedSection) ? _selectedSection : null,
                  decoration: InputDecoration(
                    labelText: 'Section (e.g. A1, A2, A3, A4)',
                    prefixIcon: const Icon(Icons.class_outlined),
                    filled: true,
                    fillColor: Colors.white,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  hint: const Text('Select Section'),
                  items: availableSections.map((sec) {
                    final yrNum = sec.length >= 2 ? sec.substring(1) : '';
                    final yrLabel = yrNum == '1'
                        ? '1st Year'
                        : yrNum == '2'
                            ? '2nd Year'
                            : yrNum == '3'
                                ? '3rd Year'
                                : yrNum == '4'
                                    ? '4th Year'
                                    : 'Section';
                    return DropdownMenuItem<String>(
                      value: sec,
                      child: Text('Section $sec ($yrLabel)'),
                    );
                  }).toList(),
                  onChanged: (val) {
                    setState(() => _selectedSection = val);
                  },
                ),
                const SizedBox(height: 14),

                // Roll Number input with instant lookup
                TextFormField(
                  controller: _rollController,
                  onChanged: _onRollChanged,
                  decoration: InputDecoration(
                    labelText: 'Roll Number (AKTU Roll / Section Roll)',
                    hintText: 'e.g. 2401100100001 or A1-01',
                    prefixIcon: const Icon(Icons.badge),
                    suffixIcon: _isSearchingRoster
                        ? const Padding(
                            padding: EdgeInsets.all(12),
                            child: SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                          )
                        : IconButton(
                            icon: const Icon(Icons.search),
                            tooltip: 'Lookup in Master Roster',
                            onPressed: () => _lookupRosterStudent(_rollController.text),
                          ),
                    filled: true,
                    fillColor: Colors.white,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  validator: (v) =>
                      v == null || v.trim().isEmpty ? 'Please enter roll number' : null,
                ),

                // Matched Student Banner
                if (_matchedRosterStudent != null) ...[
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.green.shade50,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: Colors.green.shade300),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.verified, color: Colors.green, size: 22),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Verified Roster Record: ${_matchedRosterStudent!['name']}',
                                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: Colors.green.shade900),
                              ),
                              Text(
                                'Branch ${_matchedRosterStudent!['branch_code']} (${_matchedRosterStudent!['branch_name']}) • Section ${_matchedRosterStudent!['section']} • Class Roll #${_matchedRosterStudent!['class_roll_no'] ?? "-"}',
                                style: TextStyle(fontSize: 11, color: Colors.green.shade800),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 14),

                // Name input
                TextFormField(
                  controller: _nameController,
                  decoration: InputDecoration(
                    labelText: 'Full Student Name',
                    hintText: 'e.g. Ayush Pandey',
                    prefixIcon: const Icon(Icons.person),
                    filled: true,
                    fillColor: Colors.white,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  validator: (v) =>
                      v == null || v.trim().isEmpty ? 'Please enter student name' : null,
                ),
                const SizedBox(height: 14),

                // Server URL input
                TextFormField(
                  controller: _serverController,
                  decoration: InputDecoration(
                    labelText: 'Server Base URL',
                    hintText: 'https://ayush-smart-backend.loca.lt',
                    prefixIcon: const Icon(Icons.dns),
                    helperText: 'Cloud Testing Link. Works on 4G Mobile Data.',
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
                          'App reinstalled? Restore profile:',
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
                            : const Text('Restore', style: TextStyle(fontSize: 12)),
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
//  Browse Master College Roster Bottom Sheet
// ─────────────────────────────────────────────────────────────────────────────

class _BrowseRosterSheet extends StatefulWidget {
  final String serverUrl;
  final String initialBranch;
  final String initialSection;
  final Function(Map<String, dynamic> student) onSelectStudent;

  const _BrowseRosterSheet({
    required this.serverUrl,
    required this.initialBranch,
    required this.initialSection,
    required this.onSelectStudent,
  });

  @override
  State<_BrowseRosterSheet> createState() => _BrowseRosterSheetState();
}

class _BrowseRosterSheetState extends State<_BrowseRosterSheet> {
  late String _branch;
  late String _section;
  final _searchController = TextEditingController();
  List<dynamic> _students = [];
  bool _isLoading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _branch = widget.initialBranch;
    _section = widget.initialSection;
    _fetchStudents();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _fetchStudents() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final query = _searchController.text.trim();
      final uri = Uri.parse('${widget.serverUrl}/roster/students?section=$_section&search=${Uri.encodeComponent(query)}&limit=100');
      final res = await http.get(uri, headers: kDefaultHttpHeaders).timeout(const Duration(seconds: 60));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        if (mounted) {
          setState(() {
            _students = data['students'] as List<dynamic>? ?? [];
            _isLoading = false;
          });
        }
      } else {
        if (mounted) {
          setState(() {
            _error = 'Failed to load roster (${res.statusCode})';
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Connection error: $e';
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final sections = ['$_branch 1', '$_branch 2', '$_branch 3', '$_branch 4']
        .map((s) => s.replaceAll(' ', ''))
        .toList();

    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (ctx, scrollController) {
        return Container(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Handle bar
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 12),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade300,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Select Student from Master Roster',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
              const SizedBox(height: 8),

              // Branch Selector Row
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: kBranches.entries.map((e) {
                    final isSel = e.key == _branch;
                    return Padding(
                      padding: const EdgeInsets.only(right: 6),
                      child: ChoiceChip(
                        label: Text('${e.key} (${kBranchShortNames[e.key] ?? ""})'),
                        selected: isSel,
                        onSelected: (val) {
                          if (val) {
                            setState(() {
                              _branch = e.key;
                              _section = '${e.key}1';
                            });
                            _fetchStudents();
                          }
                        },
                      ),
                    );
                  }).toList(),
                ),
              ),
              const SizedBox(height: 8),

              // Section Selector Row
              Row(
                children: sections.map((sec) {
                  final isSel = sec == _section;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: FilterChip(
                      label: Text(sec),
                      selected: isSel,
                      onSelected: (val) {
                        setState(() => _section = sec);
                        _fetchStudents();
                      },
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 10),

              // Search box
              TextField(
                controller: _searchController,
                onChanged: (_) => _fetchStudents(),
                decoration: InputDecoration(
                  hintText: 'Search by name or roll number...',
                  prefixIcon: const Icon(Icons.search, size: 20),
                  suffixIcon: _searchController.text.isNotEmpty
                      ? IconButton(
                          icon: const Icon(Icons.clear, size: 18),
                          onPressed: () {
                            _searchController.clear();
                            _fetchStudents();
                          },
                        )
                      : null,
                  isDense: true,
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                ),
              ),
              const SizedBox(height: 12),

              // List of students
              Expanded(
                child: _isLoading
                    ? const Center(child: CircularProgressIndicator())
                    : _error != null
                        ? Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Text(_error!, style: const TextStyle(color: Colors.red)),
                                const SizedBox(height: 8),
                                FilledButton.tonal(
                                  onPressed: _fetchStudents,
                                  child: const Text('Retry'),
                                ),
                              ],
                            ),
                          )
                        : _students.isEmpty
                            ? const Center(child: Text('No students found in this section.'))
                            : ListView.separated(
                                controller: scrollController,
                                itemCount: _students.length,
                                separatorBuilder: (_, __) => const Divider(height: 1),
                                itemBuilder: (ctx, i) {
                                  final s = _students[i] as Map<String, dynamic>;
                                  final isReg = s['is_registered'] == true;
                                  final classRoll = s['class_roll_no']?.toString() ?? '-';
                                  final aktuRoll = s['aktu_roll_no']?.toString() ?? '';
                                  final name = s['name'] ?? '';

                                  return ListTile(
                                    leading: CircleAvatar(
                                      backgroundColor: isReg ? Colors.green.shade100 : const Color(0xFF0F3460).withValues(alpha: 0.1),
                                      child: Text(
                                        classRoll,
                                        style: TextStyle(
                                          fontWeight: FontWeight.bold,
                                          fontSize: 12,
                                          color: isReg ? Colors.green.shade900 : const Color(0xFF0F3460),
                                        ),
                                      ),
                                    ),
                                    title: Text(
                                      name,
                                      style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                                    ),
                                    subtitle: Text(
                                      'Roll: ${aktuRoll.isNotEmpty ? aktuRoll : s['roll_no'] ?? "-"} • Section $_section',
                                      style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                                    ),
                                    trailing: isReg
                                        ? Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                            decoration: BoxDecoration(
                                              color: Colors.green.shade50,
                                              borderRadius: BorderRadius.circular(4),
                                              border: Border.all(color: Colors.green.shade300),
                                            ),
                                            child: const Text(
                                              'Registered',
                                              style: TextStyle(fontSize: 10, color: Colors.green, fontWeight: FontWeight.bold),
                                            ),
                                          )
                                        : const Icon(Icons.chevron_right, color: Colors.grey),
                                    onTap: () => widget.onSelectStudent(s),
                                  );
                                },
                              ),
              ),
            ],
          ),
        );
      },
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Main Attendance Dashboard (For Registered Students)
// ─────────────────────────────────────────────────────────────────────────────

