# 🎓 Smart Attendance System (BLE + Face Recognition + Strict Time Window)

An end-to-end intelligent attendance automation system featuring **Background ESP32 BLE Beacon Proximity Detection**, **Local Push Notifications**, **Deep Face Recognition**, **Strict Timetable Attendance Windows**, and **Full College Roster Integration** across **7 Branches** and **28 Sections**.

---

## 🌟 System Architecture

```
                                  ┌───────────────────────────┐
                                  │   ESP32 Classroom Beacon  │
                                  │ (UUID: 12345678-1234-...) │
                                  └─────────────┬─────────────┘
                                                │ BLE Proximity Advertisement
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Flutter Mobile App                              │
│                                                                             │
│  [Background BLE Service] ──(RSSI >= -75dBm)──► [Local Push Notification]   │
│                                                          │                  │
│                                                          ▼                  │
│  [API: /verify] ◄──(Captures Live Selfie & Device UUID)── [Face Scan Camera]│
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP POST /verify (Multipart Photo)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FastAPI Python Backend                            │
│                                                                             │
│  1. Strict Time Gate: Validates allowed attendance window (10 min)          │
│  2. Face Matching: 128-d Euclidean distance vs registered SQLite biometric  │
│  3. Anti-Proxy Protection: Hardware Device UUID locking                     │
│  4. Attendance Engine: Logs attendance & prevents duplicate daily scans     │
│  5. Reporting: Generates official Excel sheets (.xlsx) & emails professors   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Serves Web App & REST API
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Modern Single Page Web Dashboard                     │
│                                                                             │
│  • Timetable Manager: Branch (A-G), Year (1st-4th) & Section (A1-G4)        │
│  • Master College Roster Hub (1,706 Students Directory & Biometric Status)  │
│  • Live Classroom Radar & Attendance Grid                                   │
│  • Excel Attendance Sheet Generation & Email Automation                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏛️ IERT Prayagraj College Structure & Branch Matrix

The system includes pre-configured mappings for all **7 Engineering Branches** and **28 Sections** (spanning **1st to 4th Academic Years**):

| Branch Code | Branch Name | Short Code | Academic Years & Sections | Total Enrolled |
| :---: | :--- | :---: | :--- | :---: |
| **`A`** | Computer Science & Engineering | **CSE** | `A1` (1st Yr), `A2` (2nd Yr), `A3` (3rd Yr), `A4` (4th Yr) | 275 |
| **`B`** | Electronics Engineering | **ECE** | `B1` (1st Yr), `B2` (2nd Yr), `B3` (3rd Yr), `B4` (4th Yr) | 277 |
| **`C`** | Industrial & Production Engineering | **IPE** | `C1` (1st Yr), `C2` (2nd Yr), `C3` (3rd Yr), `C4` (4th Yr) | 204 |
| **`D`** | Mechanical Engineering | **ME** | `D1` (1st Yr), `D2` (2nd Yr), `D3` (3rd Yr), `D4` (4th Yr) | 280 |
| **`E`** | Instrumentation & Control Engineering | **ICE** | `E1` (1st Yr), `E2` (2nd Yr), `E3` (3rd Yr), `E4` (4th Yr) | 134 |
| **`F`** | Electrical Engineering | **EE** | `F1` (1st Yr), `F2` (2nd Yr), `F3` (3rd Yr), `F4` (4th Yr) | 272 |
| **`G`** | Civil Engineering | **CE** | `G1` (1st Yr), `G2` (2nd Yr), `G3` (3rd Yr), `G4` (4th Yr) | 264 |
| **Total** | **7 Engineering Branches** | | **4 Academic Years • 28 Sections** | **1,706 Students** |

---

## 🚀 Key System Capabilities

1. **Background BLE Beacon Sensing & Instant Notification**:
   - Flutter background service monitors BLE broadcasts from the classroom ESP32 beacon (`12345678-1234-1234-1234-123456789abc`).
   - When inside the classroom (`RSSI >= -75 dBm`), triggers local notification:
     > *"You are in the classroom. Tap to mark attendance."*
   - Tapping opens the selfie camera screen directly.

2. **Strict Attendance Window Enforcement**:
   - Timetable sets strict allowed attendance windows (default: **10 minutes** from lecture start).
   - Late scans past the window are rejected with `403 Forbidden` (*"Time limit exceeded"*).

3. **Master College Roster & Student Onboarding**:
   - Master directory of **1,706 students** pre-loaded with AKTU Roll, Class Roll, Branch, Section, and Year.
   - Real-time auto-complete on registration: Typing roll number instantly pulls official records.
   - **One-Tap Section Browser**: Students can browse their section list and select their name.

4. **Automated Excel Attendance Reporting**:
   - On lecture completion ("End Class"), generates formatted `.xlsx` workbooks containing:
     `S.No`, `Class Roll No`, `Primary / AKTU Roll No`, `Student Name`, `Academic Year`, `Branch`, `Section`, `Subject`, `Date`, `Scan Time`, `Biometrics Registered`, and `Attendance Status`.
   - Automatically emails the report to the course professor via SMTP.

---

## 📁 Repository Organization

```
RFID/
├── backend/                      # Python FastAPI REST Server
│   ├── main.py                  # API endpoints, SQLite schema, face recognition, timetable & excel generator
│   ├── attendance.db            # SQLite database (students, attendance, timetable, roster)
│   ├── requirements.txt         # Python dependencies
│   ├── test_time_window.py      # Unit test suite for strict time windows & verification
│   └── test_verify.py           # Verification script
├── frontend/                     # Single Page Web Application (Vanilla JS + Tailwind CSS)
│   ├── index.html               # Main dashboard UI shell
│   ├── css/style.css            # Custom theme styles
│   └── js/
│       ├── app.js               # SPA router
│       ├── api.js               # REST client for backend communication
│       ├── components/          # Navbar & Toast notification components
│       └── pages/               # Dashboard, Timetable, Register, Students, Attendance, Classroom
├── mobile_app/                   # Flutter Android Application
│   ├── lib/main.dart            # BLE background service, face camera, student dashboard & analytics
│   ├── pubspec.yaml             # Flutter packages
│   └── android/                 # Native Android manifests & permissions
├── hardware/                     # ESP32 Microcontroller Firmware
│   ├── esp32_classroom_beacon/  # Arduino .ino iBeacon transmitter sketch
│   └── esp32_ble/               # PlatformIO C++ BLE scanner project
├── SmartAttendance.apk           # Standalone Release Android APK (52.4 MB)
└── README.md                     # Complete project documentation
```

---

## 🚦 Quick Start Guide

### 1. Launch Backend Server & Web UI
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
Open **`http://localhost:8000`** in any web browser.

### 2. Run / Build Flutter Mobile App
```bash
cd mobile_app
flutter pub get
flutter run --release
```
To generate a release Android APK:
```bash
flutter build apk --release
```
The output APK will be saved at `build/app/outputs/flutter-apk/app-release.apk` (and mirrored to `d:\RFID\SmartAttendance.apk`).

### 3. Flash ESP32 Classroom Beacon
1. Open [`hardware/esp32_classroom_beacon/esp32_classroom_beacon.ino`](file:///d:/RFID/hardware/esp32_classroom_beacon/esp32_classroom_beacon.ino) in Arduino IDE.
2. Select **ESP32 Dev Module** as board.
3. Upload sketch. The onboard LED will turn ON and broadcast the classroom beacon.

---

## 🔒 Security & Data Privacy
- [`.gitignore`](file:///d:/RFID/.gitignore) strictly prevents raw roster documents, private Excel sheets, database files, and `.env` credentials from being committed to version control.

## 📂 Enterprise Directory Structure (Modular Architecture)

The system has been heavily refactored from prototype monoliths into a clean, scalable, and enterprise-grade modular architecture.

```text
/ (Root)
├── START_SERVER.bat                   ▶️ 1-click startup script for backend & web dashboard
├── attendance.db                      🗄️ SQLite Database (Students, Attendance, Timetable)
├── README.md                          📖 Project documentation
│
├── hardware/                          📟 PILLAR 1: PHYSICAL SECURITY / IOT
│   └── esp32_classroom_beacon/
│       └── esp32_classroom_beacon.ino 📡 C++ Code: ESP32 BLE iBeacon broadcasting class UUID
│
├── backend/                           🧠 PILLAR 2: SERVER & AI ENGINE (FastAPI)
│   ├── main.py                        ✅ API Entry point
│   ├── config.py & database.py        ⚙️ Core Settings & DB Connection
│   ├── schemas.py & utils.py          🛡️ Pydantic Validators & Helper functions
│   │
│   ├── routers/                       🔀 API Endpoints
│   │   ├── attendance.py              # Face match verification & live attendance logs
│   │   ├── students.py                # Student registration & deletion management
│   │   ├── timetable.py               # Dynamic strict-window class scheduling
│   │   ├── roster.py                  # Student metrics & college directory
│   │   └── admin.py                   # Secure admin overrides & locks
│   │
│   └── services/                      ⚡ Core Business Logic
│       ├── face_engine.py             👤 Ultra-fast Vectorized AI Face Index (O(1) Numpy matching)
│       ├── report_service.py          📊 Automated Excel generation & SMTP Emailing
│       └── timetable_service.py       ⏰ 10-minute strict attendance window calculations
│
├── mobile_app/lib/                    📱 PILLAR 3: STUDENT APP (Flutter)
│   ├── main.dart                      ✅ Flutter App Entry Point
│   │
│   ├── utils/
│   │   └── constants.dart             🔗 BLE UUIDs & Global Configurations
│   │
│   ├── services/
│   │   └── background_service.dart    📡 Background BLE signal scanner & Push Notifications
│   │
│   └── screens/                       📱 UI Pages
│       ├── face_scan_screen.dart      # Camera capture & biometric submission UI
│       ├── attendance_screen.dart     # Dashboard showing timetable & personal record
│       ├── register_screen.dart       # First-time biometric enrollment & roster lookup
│       └── analytics_screen.dart      # 75% shortage graphs & metrics
│
└── frontend/                          🌐 PILLAR 4: TEACHER/ADMIN DASHBOARD
    ├── index.html                     🏠 Teacher Web Portal
    ├── css/                           🎨 Styling sheets
    │
    └── js/pages/                      📜 Modular Dashboard Scripts
        ├── classroom.js               # Live tracking & active class metrics
        ├── timetable.js               # UI to schedule dynamic class windows
        ├── attendance.js              # View & download daily present/absent lists
        ├── dashboard.js               # Overall college attendance charts
        └── students.js & register.js  # Roster management & enrollment tools
```
