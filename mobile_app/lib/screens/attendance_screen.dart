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
  String _studentBranch = '';
  String _studentSection = '';
  String _studentClassRoll = '';
  String _studentYear = '';

  // Timetable State
  bool _isLoadingTimetable = false;
  Map<String, dynamic>? _currentClass;
  Map<String, dynamic>? _windowStatus;
  List<Map<String, dynamic>> _timetableList = [];
  bool _showAllDays = false;
  String _serverDay = '';
  String _serverTime = '';
  String _timetableError = '';

  List<Map<String, dynamic>> get _todayClasses {
    if (_timetableList.isEmpty) return [];
    final currentDay = _serverDay.isNotEmpty
        ? _serverDay
        : ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][DateTime.now().weekday - 1];
    return _timetableList.where((item) {
      final day = item['day']?.toString() ?? '';
      return day.toLowerCase() == currentDay.toLowerCase();
    }).toList();
  }

  // BLE Beacon State
  bool _isManualScanning = false;
  bool _isBeaconDetected = false;

  @override
  void initState() {
    super.initState();
    _loadProfile();
    _requestAllPermissions();

    _notificationSub = globalFaceScanTrigger.stream.listen((shouldOpen) {
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
    final branch = await AppSettings.getStudentBranch();
    final section = await AppSettings.getStudentSection();
    final classRoll = await AppSettings.getStudentClassRoll();
    final year = await AppSettings.getStudentYear();
    if (mounted) {
      setState(() {
        _studentName = name;
        _studentRoll = roll;
        _serverUrl = server;
        _studentBranch = branch;
        _studentSection = section;
        _studentClassRoll = classRoll;
        _studentYear = year;
      });
      _fetchLiveTimetable();
      _startManualBeaconScan();

      // Auto-sync profile with backend to keep branch/section updated
      if (server.isNotEmpty && roll.isNotEmpty) {
        _syncProfileFromServer(server, roll);
      }
    }
  }

  Future<void> _syncProfileFromServer(String serverUrl, String rollNo) async {
    try {
      final uri = Uri.parse('$serverUrl/students/$rollNo');
      final res = await http.get(uri, headers: kDefaultHttpHeaders).timeout(const Duration(seconds: 60));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        final newBranch = (data['branch_code'] ?? '').toString();
        final newSection = (data['section'] ?? '').toString();
        final newClassRoll = (data['class_roll_no'] ?? '').toString();
        final newYear = (data['year'] ?? '').toString();
        final newName = (data['name'] ?? '').toString();

        bool hasChange = false;
        if (newSection.isNotEmpty && newSection != _studentSection) hasChange = true;
        if (newBranch.isNotEmpty && newBranch != _studentBranch) hasChange = true;
        if (newName.isNotEmpty && newName != _studentName) hasChange = true;

        if (hasChange && mounted) {
          await AppSettings.saveProfile(
            name: newName.isNotEmpty ? newName : _studentName,
            rollNo: rollNo,
            serverUrl: serverUrl,
            branch: newBranch,
            section: newSection,
            classRoll: newClassRoll,
            year: newYear,
          );
          setState(() {
            _studentName = newName.isNotEmpty ? newName : _studentName;
            _studentBranch = newBranch;
            _studentSection = newSection;
            _studentClassRoll = newClassRoll;
            _studentYear = newYear;
          });
          _fetchLiveTimetable();
        }
      }
    } catch (_) {}
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
      String url = '$_serverUrl/timetable';
      final params = <String, String>{};
      if (_studentSection.isNotEmpty) params['section'] = _studentSection;
      if (_studentBranch.isNotEmpty) params['branch_code'] = _studentBranch;
      if (_studentYear.isNotEmpty) params['year'] = _studentYear;
      if (params.isNotEmpty) {
        url += '?${Uri(queryParameters: params).query}';
      }
      final uri = Uri.parse(url);
      final response = await http.get(uri, headers: kDefaultHttpHeaders).timeout(const Duration(seconds: 60));
      if (response.statusCode == 200) {
        try {
          final data = jsonDecode(response.body) as Map<String, dynamic>;
          final currentSlot = data['current_slot'] as Map<String, dynamic>?;
          final rawList = data['timetable'] as List<dynamic>?;
          List<Map<String, dynamic>> parsedList = [];
          if (rawList != null) {
            parsedList = rawList.map((e) => Map<String, dynamic>.from(e as Map)).toList();
            // Client-side guarantee: Only show classes for this student's section or All Sections
            if (_studentSection.isNotEmpty) {
              final mySec = _studentSection.trim().toUpperCase();
              final myBranch = _studentBranch.trim().toUpperCase();
              parsedList = parsedList.where((item) {
                final sec = (item['section'] ?? '').toString().trim().toUpperCase();
                final br = (item['branch_code'] ?? '').toString().trim().toUpperCase();
                if (sec.isNotEmpty && sec != 'ALL' && sec != 'ALL SECTIONS') {
                  return sec == mySec;
                }
                if (br.isNotEmpty && br != 'ALL' && br != 'ALL BRANCHES' && myBranch.isNotEmpty) {
                  return br == myBranch;
                }
                return true;
              }).toList();
            }
          }
          if (mounted) {
            setState(() {
              _timetableError = '';
              _timetableList = parsedList;
              if (currentSlot != null) {
                _serverDay = currentSlot['day'] ?? '';
                _serverTime = currentSlot['time'] ?? '';
                _currentClass = currentSlot['class'] as Map<String, dynamic>?;
                _windowStatus = currentSlot['window_status'] as Map<String, dynamic>?;
              }
            });
          }
        } catch (e) {
          debugPrint('[TIMETABLE] Parse error: $e');
          if (mounted) {
            setState(() {
              _timetableError = 'Invalid server response';
            });
          }
        }
      } else {
        if (mounted) {
          setState(() {
            _timetableError = 'Server offline (${response.statusCode})';
          });
        }
      }
    } catch (e) {
      debugPrint('[TIMETABLE] Failed to fetch: $e');
      if (mounted) {
        setState(() {
          _timetableError = 'Connection error';
        });
      }
    } finally {
      if (mounted) setState(() => _isLoadingTimetable = false);
    }
  }

  Future<void> _startManualBeaconScan() async {
    if (_isManualScanning) return;
    setState(() => _isManualScanning = true);

    final cleanTargetUUID = kBeaconUUID.replaceAll('-', '').toLowerCase();
    bool found = false;
    StreamSubscription? scanSub;
    try {
      if (await FlutterBluePlus.adapterState.first != BluetoothAdapterState.on) {
        setState(() {
          _isBeaconDetected = false;
          _isManualScanning = false;
        });
        return;
      }

      scanSub = FlutterBluePlus.scanResults.listen((results) {
        for (final r in results) {
          bool matched = false;
          for (final u in r.advertisementData.serviceUuids) {
            if (u.toString().replaceAll('-', '').toLowerCase() == cleanTargetUUID) {
              matched = true;
              break;
            }
          }
          if (!matched) {
            final mfg = r.advertisementData.manufacturerData;
            if (mfg.containsKey(0x004C) || mfg.containsKey(0x4C00)) {
              final bytes = mfg[0x004C] ?? mfg[0x4C00];
              if (bytes != null && bytes.length >= 20) {
                final uuidBytes = bytes.sublist(2, 18);
                if (uuidBytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join() == cleanTargetUUID) {
                  matched = true;
                }
              }
            }
          }
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
            break;
          }
        }
      });

      await FlutterBluePlus.startScan(
        timeout: const Duration(seconds: 60),
        androidUsesFineLocation: true,
      );
      await Future.delayed(const Duration(seconds: 4));
    } catch (e) {
      debugPrint('[BLE_SCAN] Error: $e');
    } finally {
      await FlutterBluePlus.stopScan();
      await scanSub?.cancel();
      if (mounted) {
        setState(() {
          _isManualScanning = false;
          _isBeaconDetected = found;
        });
      }
    }
  void _promptAdminPasscodeAndShowSettings() {
    final pinController = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.admin_panel_settings, color: Color(0xFF0F3460)),
            SizedBox(width: 8),
            Text('Admin Settings', style: TextStyle(fontSize: 16)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Enter admin password to configure server settings:', style: TextStyle(fontSize: 12)),
            const SizedBox(height: 10),
            TextField(
              controller: pinController,
              obscureText: true,
              autofocus: true,
              decoration: const InputDecoration(
                hintText: 'Admin Password',
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              final pin = pinController.text.trim();
              if (pin == 'admin123' || pin == 'Ayush' || pin == 'H2so4.Al2so4' || pin == '2026') {
                Navigator.pop(ctx);
                _showSettingsDialog();
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Incorrect admin password.'), backgroundColor: Colors.red),
                );
              }
            },
            child: const Text('Unlock'),
          ),
        ],
      ),
    );
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
                hintText: 'https://ayush-smart-backend.loca.lt',
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
            const SizedBox(height: 6),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () {
                  controller.text = kDefaultApiBaseUrl;
                },
                icon: const Icon(Icons.cloud_sync, size: 16),
                label: const Text('Reset to Cloud URL (ayush-smart-backend)', style: TextStyle(fontSize: 11)),
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
    final subjectName = _timetableError.isNotEmpty
        ? '⚠️ Cloud Server Offline'
        : (hasActiveSubject ? _currentClass!['subject'] : 'No Class Scheduled');
    final teacherEmail = hasActiveSubject ? _currentClass!['teacher_email'] ?? '' : '';
    final isWindowOpen = _timetableError.isEmpty && _windowStatus != null && _windowStatus!['is_open'] == true;
    final windowMessage = _timetableError.isNotEmpty
        ? 'Cannot connect to college server. Swipe down to refresh.'
        : (_windowStatus != null ? _windowStatus!['message'] ?? '' : 'No active attendance window.');

    String classTimingStr = '';
    String windowTimingStr = '';
    if (hasActiveSubject) {
      if (_currentClass!['timing_12h'] != null && _currentClass!['timing_12h'].toString().isNotEmpty) {
        classTimingStr = _currentClass!['timing_12h'].toString();
      } else if (_currentClass!['time_label'] != null && _currentClass!['time_label'].toString().isNotEmpty) {
        classTimingStr = _currentClass!['time_label'].toString();
      } else {
        final startH = _currentClass!['hour'] ?? 0;
        final startM = _currentClass!['start_minute'] ?? 0;
        final endH = _currentClass!['end_hour'] ?? (startH + 1);
        final endM = _currentClass!['end_minute'] ?? 0;
        classTimingStr = '${startH.toString().padLeft(2, '0')}:${startM.toString().padLeft(2, '0')} - ${endH.toString().padLeft(2, '0')}:${endM.toString().padLeft(2, '0')}';
      }

      if (_windowStatus != null && _windowStatus!['window_end'] != null) {
        windowTimingStr = _windowStatus!['window_end'].toString();
      } else if (_currentClass!['window_end_time'] != null) {
        windowTimingStr = _currentClass!['window_end_time'].toString();
      }
    }

    return Scaffold(
      appBar: AppBar(
        title: GestureDetector(
          onLongPress: _promptAdminPasscodeAndShowSettings,
          child: const Text('Smart Attendance'),
        ),
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
            icon: const Icon(Icons.logout),
            tooltip: 'Log out',
            onPressed: () async {
              final confirm = await showDialog<bool>(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('Log out?'),
                  content: const Text('Do you want to switch or log out student profile?'),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                    FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Log out')),
                  ],
                ),
              );
              if (confirm == true) {
                await AppSettings.clearProfile();
                if (!context.mounted) return;
                Navigator.pushReplacement(
                  context,
                  MaterialPageRoute(builder: (_) => const StudentRegisterScreen()),
                );
              }
            },
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
                                'Roll No: ${_studentRoll.isNotEmpty ? _studentRoll : "Not Registered"}${_studentClassRoll.isNotEmpty ? " • Class #$_studentClassRoll" : ""}',
                                style: TextStyle(
                                  color: Colors.grey.shade700,
                                  fontWeight: FontWeight.w600,
                                  fontSize: 13,
                                ),
                              ),
                              if (_studentBranch.isNotEmpty || _studentSection.isNotEmpty || _studentYear.isNotEmpty) ...[
                                const SizedBox(height: 4),
                                Row(
                                  children: [
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: const Color(0xFFE94560).withValues(alpha: 0.12),
                                        borderRadius: BorderRadius.circular(6),
                                        border: Border.all(color: const Color(0xFFE94560).withValues(alpha: 0.4)),
                                      ),
                                      child: Text(
                                        AppSettings.getYearLabel(_studentYear.isNotEmpty ? _studentYear : _studentSection),
                                        style: const TextStyle(
                                          color: Color(0xFFE94560),
                                          fontWeight: FontWeight.bold,
                                          fontSize: 11,
                                        ),
                                      ),
                                    ),
                                    if (_studentSection.isNotEmpty) ...[
                                      const SizedBox(width: 6),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: const Color(0xFF0F3460).withValues(alpha: 0.1),
                                          borderRadius: BorderRadius.circular(6),
                                          border: Border.all(color: const Color(0xFF0F3460).withValues(alpha: 0.3)),
                                        ),
                                        child: Text(
                                          'Section $_studentSection',
                                          style: const TextStyle(
                                            color: Color(0xFF0F3460),
                                            fontWeight: FontWeight.bold,
                                            fontSize: 11,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                                if (_studentBranch.isNotEmpty) ...[
                                  const SizedBox(height: 3),
                                  Text(
                                    '${kBranches[_studentBranch] ?? _studentBranch} (${kBranchShortNames[_studentBranch] ?? _studentBranch})',
                                    style: TextStyle(
                                      color: Colors.grey.shade800,
                                      fontWeight: FontWeight.w600,
                                      fontSize: 11.5,
                                    ),
                                  ),
                                ],
                              ],
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
                        if (classTimingStr.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF1F5F9),
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: const Color(0xFFCBD5E1)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.access_time_filled, size: 16, color: Color(0xFF0F3460)),
                                const SizedBox(width: 6),
                                const Text(
                                  'Class Timing: ',
                                  style: TextStyle(
                                    color: Colors.black87,
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                Text(
                                  classTimingStr,
                                  style: const TextStyle(
                                    color: Color(0xFF0F3460),
                                    fontSize: 12.5,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                        if (teacherEmail.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(
                            'Teacher: $teacherEmail',
                            style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                          ),
                        ],
                        const SizedBox(height: 10),
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
                                      ? (windowTimingStr.isNotEmpty
                                          ? 'Window OPEN — Mark attendance before $windowTimingStr!'
                                          : 'Window OPEN — You can mark attendance now!')
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
                if (_timetableError.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    decoration: BoxDecoration(
                      color: Colors.red.shade50,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.red.shade200),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.cloud_off, color: Colors.red.shade700, size: 22),
                        const SizedBox(width: 10),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'College Server Offline',
                                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: Color(0xFF991B1B)),
                              ),
                              SizedBox(height: 2),
                              Text(
                                'Unable to connect to college attendance service. Please check your internet or retry.',
                                style: TextStyle(fontSize: 10.5, color: Colors.black87),
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.refresh, size: 20, color: Color(0xFF0F3460)),
                          tooltip: 'Retry Connection',
                          onPressed: () {
                            _fetchLiveTimetable();
                            _startManualBeaconScan();
                          },
                        ),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 14),

                // 2b. Scheduled Classes List Card (Today / Full Timetable)
                Card(
                  elevation: 2,
                  color: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                    side: BorderSide(color: Colors.grey.shade300, width: 1),
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
                                const Icon(Icons.calendar_today, color: Color(0xFF0F3460), size: 18),
                                const SizedBox(width: 8),
                                Text(
                                  _showAllDays
                                      ? 'Weekly Schedule'
                                      : "Today's Schedule (${_serverDay.isNotEmpty ? _serverDay : 'Today'})",
                                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                                ),
                              ],
                            ),
                            TextButton.icon(
                              onPressed: () => setState(() => _showAllDays = !_showAllDays),
                              icon: Icon(_showAllDays ? Icons.today : Icons.view_week, size: 14),
                              label: Text(
                                _showAllDays ? 'Show Today' : 'All Days',
                                style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold),
                              ),
                              style: TextButton.styleFrom(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                minimumSize: Size.zero,
                                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        () {
                          final listToDisplay = _showAllDays ? _timetableList : _todayClasses;
                          if (listToDisplay.isEmpty) {
                            return Padding(
                              padding: const EdgeInsets.symmetric(vertical: 12),
                              child: Center(
                                child: Text(
                                  _isLoadingTimetable
                                      ? 'Loading schedule from server...'
                                      : (_showAllDays ? 'No timetable entries found.' : 'No classes scheduled for today.\nTap "All Days" to view the full schedule.'),
                                  textAlign: TextAlign.center,
                                  style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                                ),
                              ),
                            );
                          }
                          return Column(
                            children: listToDisplay.map((item) {
                              final subj = item['subject']?.toString() ?? 'Class';
                              final isLive = _currentClass != null &&
                                  _currentClass!['subject'] == subj &&
                                  _currentClass!['hour'] == item['hour'];
                              final timeStr = item['timing_12h'] ?? item['time_label'] ?? '${item['hour']}:00';
                              final teacher = item['teacher_email']?.toString() ?? '';
                              final sec = item['section']?.toString() ?? '';
                              final dayStr = item['day']?.toString() ?? '';

                              return Container(
                                margin: const EdgeInsets.only(bottom: 8),
                                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                                decoration: BoxDecoration(
                                  color: isLive ? Colors.green.shade50 : const Color(0xFFF8F9FA),
                                  borderRadius: BorderRadius.circular(10),
                                  border: Border.all(
                                    color: isLive ? Colors.green.shade400 : Colors.grey.shade200,
                                    width: isLive ? 1.5 : 1,
                                  ),
                                ),
                                child: Row(
                                  children: [
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
                                      decoration: BoxDecoration(
                                        color: isLive ? Colors.green.shade700 : const Color(0xFF16213E),
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        timeStr,
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 11,
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 10),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Row(
                                            children: [
                                              Flexible(
                                                child: Text(
                                                  subj,
                                                  style: TextStyle(
                                                    fontWeight: FontWeight.bold,
                                                    fontSize: 13,
                                                    color: isLive ? Colors.green.shade900 : Colors.black87,
                                                  ),
                                                  overflow: TextOverflow.ellipsis,
                                                ),
                                              ),
                                              if (_showAllDays && dayStr.isNotEmpty) ...[
                                                const SizedBox(width: 6),
                                                Container(
                                                  padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                                                  decoration: BoxDecoration(
                                                    color: Colors.grey.shade200,
                                                    borderRadius: BorderRadius.circular(4),
                                                  ),
                                                  child: Text(
                                                    dayStr,
                                                    style: TextStyle(fontSize: 9, color: Colors.grey.shade700),
                                                  ),
                                                ),
                                              ],
                                            ],
                                          ),
                                          if (teacher.isNotEmpty || (sec.isNotEmpty && sec != 'All Sections'))
                                            Padding(
                                              padding: const EdgeInsets.only(top: 2),
                                              child: Text(
                                                [
                                                  if (sec.isNotEmpty && sec != 'All Sections') 'Sec: $sec',
                                                  if (teacher.isNotEmpty) teacher,
                                                ].join(' • '),
                                                style: TextStyle(fontSize: 10, color: Colors.grey.shade600),
                                                overflow: TextOverflow.ellipsis,
                                              ),
                                            ),
                                        ],
                                      ),
                                    ),
                                    if (isLive)
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: Colors.green.shade600,
                                          borderRadius: BorderRadius.circular(6),
                                        ),
                                        child: const Text(
                                          '● LIVE',
                                          style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                                        ),
                                      ),
                                  ],
                                ),
                              );
                            }).toList(),
                          );
                        }(),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 14),

                // Location / Classroom Presence Badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: _isBeaconDetected ? Colors.green.shade50 : Colors.amber.shade50,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: _isBeaconDetected ? Colors.green.shade300 : Colors.amber.shade400,
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        _isBeaconDetected ? Icons.check_circle : Icons.bluetooth_searching,
                        color: _isBeaconDetected ? Colors.green.shade700 : Colors.amber.shade800,
                        size: 20,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          _isBeaconDetected
                              ? 'Present in Classroom (Verified)'
                              : (_isManualScanning
                                  ? 'Checking Classroom Bluetooth...'
                                  : 'Not in Classroom (Turn ON Bluetooth)'),
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.bold,
                            color: _isBeaconDetected ? Colors.green.shade900 : Colors.amber.shade900,
                          ),
                        ),
                      ),
                      if (_isManualScanning)
                        const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      else if (!_isBeaconDetected)
                        TextButton(
                          onPressed: _startManualBeaconScan,
                          style: TextButton.styleFrom(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            minimumSize: Size.zero,
                            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          ),
                          child: const Text('Re-check', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 18),

                // Primary Action: Face Scan Button
                SizedBox(
                  height: 54,
                  child: FilledButton.icon(
                    onPressed: () async {
                      if (!_isBeaconDetected) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Checking classroom presence... Please make sure Bluetooth is ON.'),
                            duration: Duration(seconds: 2),
                          ),
                        );
                        await _startManualBeaconScan();
                      }
                      if (!_isBeaconDetected) {
                        if (!context.mounted) return;
                        showDialog(
                          context: context,
                          builder: (ctx) => AlertDialog(
                            title: const Row(
                              children: [
                                Icon(Icons.location_off, color: Colors.red, size: 28),
                                SizedBox(width: 10),
                                Text('Not in Classroom!', style: TextStyle(fontSize: 18)),
                              ],
                            ),
                            content: const Text(
                              'You must be physically present inside the classroom with Bluetooth turned ON to mark attendance.\n\nPlease step inside the lecture hall and try again.',
                            ),
                            actions: [
                              TextButton(
                                onPressed: () {
                                  Navigator.pop(ctx);
                                  _startManualBeaconScan();
                                },
                                child: const Text('Scan Again'),
                              ),
                              TextButton(
                                onPressed: () => Navigator.pop(ctx),
                                child: const Text('OK'),
                              ),
                            ],
                          ),
                        );
                        return;
                      }

                      if (!context.mounted) return;
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => const FaceScanScreen(),
                        ),
                      );
                    },
                    style: FilledButton.styleFrom(
                      backgroundColor: _isBeaconDetected ? const Color(0xFFE94560) : Colors.blueGrey,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    icon: const Icon(Icons.camera_alt, size: 24),
                    label: Text(
                      _isBeaconDetected ? 'Mark Attendance (Face Scan)' : 'Check Presence & Mark Attendance',
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
                const SizedBox(height: 12),

                // Analytics & 75% Tracker Button
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
                            branch: _studentBranch,
                            section: _studentSection,
                            year: _studentYear.isNotEmpty ? _studentYear : _studentSection,
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

