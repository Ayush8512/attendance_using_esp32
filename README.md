# 🎓 Smart Attendance System (BLE + Face Recognition + Strict Time Window)

An end-to-end intelligent attendance automation system featuring **Background ESP32 BLE Beacon Proximity Detection**, **Local Push Notifications**, **Deep Face Recognition**, **Strict Timetable Attendance Windows**, and **Full College Roster Integration** across **7 Branches** and **28 Sections**.

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


## 📂 Repository Organization (Modular Architecture)

```text
RFID/
├── backend/                           # Python FastAPI REST Server (Modularized)
│   ├── main.py                        # API Entry point
│   ├── config.py & database.py        # Core Settings & DB Connection
│   ├── schemas.py & utils.py          # Pydantic Validators & Helper functions
│   ├── routers/                       # API Endpoints
│   │   ├── attendance.py              # Face match verification & live attendance logs
│   │   ├── students.py                # Student registration & deletion management
│   │   ├── timetable.py               # Dynamic strict-window class scheduling
│   │   ├── roster.py                  # Student metrics & college directory
│   │   └── admin.py                   # Secure admin overrides & locks
│   └── services/                      # Core Business Logic
│       ├── face_engine.py             # Ultra-fast Vectorized AI Face Index (O(1) Numpy)
│       ├── report_service.py          # Automated Excel generation & SMTP Emailing
│       └── timetable_service.py       # 10-minute strict attendance window calculations
│
├── mobile_app/                        # Flutter Android Application
│   ├── lib/
│   │   ├── main.dart                  # Flutter App Entry Point
│   │   ├── utils/constants.dart       # BLE UUIDs & Global Configurations
│   │   ├── services/                  # Background BLE signal scanner & Push Notifications
│   │   └── screens/                   # UI Pages (Dashboard, Camera, Forms, Analytics)
│   ├── pubspec.yaml                   # Flutter packages
│   └── android/                       # Native Android manifests & permissions
│
├── frontend/                          # Single Page Web Application (Vanilla JS + Tailwind)
│   ├── index.html                     # Teacher Web Portal UI shell
│   ├── css/                           # Styling sheets
│   └── js/pages/                      # Modular Dashboard Scripts
│       ├── classroom.js               # Live tracking & active class metrics
│       ├── timetable.js               # UI to schedule dynamic class windows
│       ├── attendance.js              # View & download daily present/absent lists
│       ├── dashboard.js               # Overall college attendance charts
│       └── students.js & register.js  # Roster management & enrollment tools
│
├── hardware/                          # ESP32 Microcontroller Firmware
│   └── esp32_classroom_beacon/        # Arduino .ino iBeacon transmitter sketch
│
├── attendance.db                      # SQLite database (students, attendance, timetable)
├── START_SERVER.bat                   # 1-click startup script for backend & web dashboard
├── SmartAttendance.apk                # Standalone Release Android APK (52.7 MB)
└── README.md                          # Complete project documentation
```

