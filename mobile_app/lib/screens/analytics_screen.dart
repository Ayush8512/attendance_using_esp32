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
class StudentAnalyticsScreen extends StatefulWidget {
  final String serverUrl;
  final String rollNo;
  final String studentName;
  final String branch;
  final String section;
  final String year;

  const StudentAnalyticsScreen({
    super.key,
    required this.serverUrl,
    required this.rollNo,
    required this.studentName,
    this.branch = '',
    this.section = '',
    this.year = '',
  });

  @override
  State<StudentAnalyticsScreen> createState() => _StudentAnalyticsScreenState();
}

class _StudentAnalyticsScreenState extends State<StudentAnalyticsScreen> {
  bool _isLoading = true;
  bool _isOfflineCached = false;
  String? _cachedTimestamp;
  String? _errorMessage;
  Map<String, dynamic>? _analyticsData;

  @override
  void initState() {
    super.initState();
    _loadCachedAnalyticsThenFetch();
  }

  Future<void> _loadCachedAnalyticsThenFetch() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cachedJsonStr = prefs.getString('cached_analytics_${widget.rollNo}');
      final savedTime = prefs.getString('cached_analytics_time_${widget.rollNo}');
      if (cachedJsonStr != null && cachedJsonStr.isNotEmpty) {
        final data = jsonDecode(cachedJsonStr) as Map<String, dynamic>;
        if (mounted) {
          setState(() {
            _analyticsData = data;
            _isOfflineCached = true;
            _cachedTimestamp = savedTime;
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      debugPrint('[ANALYTICS] Cache load error: $e');
    }
    // Now fetch fresh data from server (in background if we already have offline cached data)
    _loadAnalytics(isBackgroundRefresh: _analyticsData != null);
  }

  Future<void> _loadAnalytics({bool isBackgroundRefresh = false}) async {
    if (!isBackgroundRefresh || _analyticsData == null) {
      setState(() {
        _isLoading = true;
        _errorMessage = null;
      });
    }

    try {
      final uri = Uri.parse('${widget.serverUrl}/students/${widget.rollNo}/analytics');
      final res = await http.get(uri, headers: kDefaultHttpHeaders).timeout(const Duration(seconds: 15));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        try {
          final prefs = await SharedPreferences.getInstance();
          await prefs.setString('cached_analytics_${widget.rollNo}', res.body);
          final now = DateTime.now();
          final formattedTime = '${now.day.toString().padLeft(2, '0')}/${now.month.toString().padLeft(2, '0')}/${now.year} ${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';
          await prefs.setString('cached_analytics_time_${widget.rollNo}', formattedTime);
          _cachedTimestamp = formattedTime;
        } catch (_) {}

        if (mounted) {
          setState(() {
            _analyticsData = data;
            _isLoading = false;
            _isOfflineCached = false;
            _errorMessage = null;
          });
        }
      } else {
        _handleAnalyticsError(res.statusCode, res.body);
      }
    } catch (e) {
      _handleAnalyticsError(null, e.toString());
    }
  }

  void _handleAnalyticsError(int? statusCode, String raw) {
    if (!mounted) return;

    // RESILIENT OFFLINE MODE: If we have previous or cached records, NEVER wipe them!
    if (_analyticsData != null) {
      setState(() {
        _isOfflineCached = true;
        _isLoading = false;
        _errorMessage = null;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: const [
              Icon(Icons.cloud_off, color: Colors.white, size: 18),
              SizedBox(width: 8),
              Expanded(
                child: Text('Server offline. Showing last saved records.'),
              ),
            ],
          ),
          duration: const Duration(seconds: 3),
          backgroundColor: Colors.blueGrey.shade800,
        ),
      );
      return;
    }

    String err = 'Failed to load analytics';
    if (statusCode != null) {
      try {
        err = jsonDecode(raw)['detail'] ?? 'Server error ($statusCode)';
      } catch (_) {
        if (statusCode == 502 || statusCode == 503 || raw.contains('502') || raw.contains('503') || raw.contains('Tunnel Unavailable')) {
          err = 'Cloud Tunnel is currently offline ($statusCode).\nPlease ensure START_SYSTEM.bat is running on your server.';
        } else {
          err = 'Server returned error ($statusCode)';
        }
      }
    } else {
      err = 'Unable to connect to server. Check your network connection.';
    }

    setState(() {
      _errorMessage = err;
      _isLoading = false;
    });
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
            onPressed: _isLoading ? null : () => _loadAnalytics(isBackgroundRefresh: false),
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
                  onRefresh: () => _loadAnalytics(isBackgroundRefresh: false),
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (_isOfflineCached)
                        Container(
                          margin: const EdgeInsets.only(bottom: 14),
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                          decoration: BoxDecoration(
                            color: Colors.amber.shade50,
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(color: Colors.amber.shade300),
                          ),
                          child: Row(
                            children: [
                              Icon(Icons.cloud_off_rounded, size: 20, color: Colors.amber.shade900),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      'Offline Mode — Viewing Saved Records',
                                      style: TextStyle(
                                        fontSize: 12,
                                        fontWeight: FontWeight.bold,
                                        color: Colors.amber.shade900,
                                      ),
                                    ),
                                    if (_cachedTimestamp != null)
                                      Text(
                                        'Last synced: $_cachedTimestamp',
                                        style: TextStyle(
                                          fontSize: 11,
                                          color: Colors.amber.shade800,
                                        ),
                                      ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
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
                                  'Roll No: ${widget.rollNo}${widget.section.isNotEmpty ? " • Section ${widget.section}" : ""}',
                                  style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  '${AppSettings.getYearLabel(widget.year.isNotEmpty ? widget.year : widget.section)}${widget.branch.isNotEmpty ? " • ${kBranches[widget.branch] ?? widget.branch}" : ""}',
                                  style: const TextStyle(
                                    color: Color(0xFF0F3460),
                                    fontWeight: FontWeight.bold,
                                    fontSize: 12,
                                  ),
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
