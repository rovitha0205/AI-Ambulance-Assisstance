from flask import Flask, render_template, abort, Response, jsonify, request
from ai.rule_engine import evaluate_risk
from ai.combined_diagnosis import build_combined_diagnosis
from ml.predict import predict_risk_ml
from hardware.esp32_firmware import VirtualESP32
from camera_ai.diagnostic_engine import generate_diagnosis
import json
import os
import re
import sqlite3
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen
from hardware.sensors import (
    HeartRateSensor,
    SpO2Sensor,
    TemperatureSensor,
    RespirationSensor,
    BloodPressureSensor,
    ECGSensor
)
esp32 = VirtualESP32()
app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join("data", "patients.db")
CAMERA_REPORT_PATH = os.path.join(BASE_DIR, "camera_ai", "camera_report.json")

cv2 = None
CameraAnalysisEngine = None
CAMERA_IMPORT_ERROR = None


def initialize_camera_dependencies():
    global cv2, CameraAnalysisEngine, CAMERA_IMPORT_ERROR

    if cv2 is not None and CameraAnalysisEngine is not None:
        return True

    try:
        import cv2 as cv2_module
        from camera_ai.camera_core import CameraAnalysisEngine as engine_class

        cv2 = cv2_module
        CameraAnalysisEngine = engine_class
        CAMERA_IMPORT_ERROR = None
        return True
    except Exception as exc:
        CAMERA_IMPORT_ERROR = str(exc)
        return False

# ----------------------------
# Load Camera Report
# ----------------------------
def load_camera_report():
    path = os.path.join(BASE_DIR, "camera_ai", "camera_report.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                report = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

        bleeding_risk = str(report.get("bleeding_risk", "Pending")).title()
        movement_risk = str(report.get("movement_risk", "Pending")).title()
        posture_risk = str(report.get("posture_risk", "Pending")).title()

        risk_order = {"Pending": 0, "Low": 1, "Medium": 2, "High": 3}
        overall_risk = max(
            [bleeding_risk, movement_risk, posture_risk],
            key=lambda level: risk_order.get(level, 0)
        )

        summary = report.get("summary")
        if not summary:
            summary = [
                f"Visual analysis indicates {bleeding_risk.lower()} bleeding risk.",
                f"Movement pattern classified as {movement_risk.lower()} risk.",
                f"Body posture assessment shows {posture_risk.lower()} risk."
            ]

        # Load diagnosis from report or generate it fresh
        diagnosis = report.get("diagnosis")
        if not diagnosis:
            diagnosis = generate_diagnosis(bleeding_risk, movement_risk, posture_risk)

        return {
            "bleeding_risk": bleeding_risk,
            "movement_risk": movement_risk,
            "posture_risk": posture_risk,
            "overall_risk": overall_risk,
            "analysis_quality": report.get("analysis_quality"),
            "summary": summary,
            "diagnosis": diagnosis
        }
    return None


def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection

# ----------------------------
# Dummy Patient Records
# ----------------------------
PATIENT_RECORDS = [
    {
        "id": "GOV-8821-01",
        "name": "John Doe",
        "age": 45,
        "dob": "1981-05-14",
        "past_conditions": "Hypertension, Type 2 Diabetes",
        "allergies": "Penicillin, Peanuts",
        "recent_report": "Stable cardiac history; last checkup 3 months ago."
    }
]

# ----------------------------
# Historical Patient Records for Analytics
# ----------------------------
HISTORICAL_PATIENT_RECORDS = [
    {"patient_id": "PAT-001", "name": "Robert Johnson", "date": "2026-02-10", "condition": "Cardiac Arrest", "accuracy": 92, "response_time": 4, "status": "Recovered"},
    {"patient_id": "PAT-002", "name": "Sarah Williams", "date": "2026-02-12", "condition": "Stroke", "accuracy": 88, "response_time": 7, "status": "Recovered"},
    {"patient_id": "PAT-003", "name": "Michael Brown", "date": "2026-02-14", "condition": "Trauma", "accuracy": 85, "response_time": 5, "status": "Recovering"},
    {"patient_id": "PAT-004", "name": "Emily Davis", "date": "2026-02-15", "condition": "Respiratory", "accuracy": 90, "response_time": 3, "status": "Recovered"},
    {"patient_id": "PAT-005", "name": "James Wilson", "date": "2026-02-16", "condition": "Cardiac Arrest", "accuracy": 95, "response_time": 6, "status": "Recovered"},
    {"patient_id": "PAT-006", "name": "Lisa Anderson", "date": "2026-02-17", "condition": "Stroke", "accuracy": 87, "response_time": 8, "status": "Ongoing"},
    {"patient_id": "PAT-007", "name": "David Martinez", "date": "2026-02-18", "condition": "Trauma", "accuracy": 91, "response_time": 4, "status": "Recovered"},
    {"patient_id": "PAT-008", "name": "Jennifer Taylor", "date": "2026-02-19", "condition": "Respiratory", "accuracy": 89, "response_time": 5, "status": "Recovered"},
]

CONDITION_DETAILS = {
    "Undifferentiated Chest Pain/Tachycardia": {
        "diagnosis_detail": "Acute cardiocirculatory stress syndrome identified from live physiology without relying on historical comorbidity records.",
        "medications": [
            {"name": "Aspirin", "dosage": "300 mg", "frequency": "Once (if indicated)", "purpose": "Early antiplatelet support in suspected ACS pattern"},
            {"name": "Nitroglycerin", "dosage": "0.4 mg SL", "frequency": "Every 5 min x3 (if suitable)", "purpose": "Symptomatic relief for chest pain/hemodynamic strain"},
            {"name": "Metoprolol", "dosage": "25 mg", "frequency": "As directed", "purpose": "Rate control when tachyarrhythmia pattern persists"}
        ]
    },
    "Acute Neurological Deficit": {
        "diagnosis_detail": "Sudden neurological syndrome requiring rapid imaging and bedside neuro checks independent of prior diagnosis history.",
        "medications": [
            {"name": "Labetalol", "dosage": "10-20 mg IV", "frequency": "As directed", "purpose": "Blood pressure control in acute neuro presentations"},
            {"name": "Mannitol", "dosage": "0.5-1 g/kg", "frequency": "As directed", "purpose": "Intracranial pressure support when clinically indicated"},
            {"name": "Normal Saline", "dosage": "500 mL", "frequency": "As needed", "purpose": "Maintain perfusion pending definitive imaging"}
        ]
    },
    "Cardiac Arrest": {
        "diagnosis_detail": "Acute cardiac event with rhythm instability requiring immediate ACLS protocol.",
        "medications": [
            {"name": "Aspirin", "dosage": "75 mg", "frequency": "Once daily", "purpose": "Antiplatelet support"},
            {"name": "Atorvastatin", "dosage": "20 mg", "frequency": "Nightly", "purpose": "Lipid control"},
            {"name": "Metoprolol", "dosage": "25 mg", "frequency": "Twice daily", "purpose": "Rate and BP control"}
        ]
    },
    "Stroke": {
        "diagnosis_detail": "Suspected ischemic neurological event with motor and speech monitoring required.",
        "medications": [
            {"name": "Clopidogrel", "dosage": "75 mg", "frequency": "Once daily", "purpose": "Secondary stroke prevention"},
            {"name": "Rosuvastatin", "dosage": "10 mg", "frequency": "Nightly", "purpose": "Vascular risk reduction"},
            {"name": "Amlodipine", "dosage": "5 mg", "frequency": "Once daily", "purpose": "Blood pressure management"}
        ]
    },
    "Trauma": {
        "diagnosis_detail": "Multi-system trauma with pain, bleeding, and mobility risk under serial monitoring.",
        "medications": [
            {"name": "Paracetamol", "dosage": "650 mg", "frequency": "Every 8 hours", "purpose": "Pain and fever control"},
            {"name": "Ceftriaxone", "dosage": "1 g", "frequency": "Twice daily", "purpose": "Infection prophylaxis"},
            {"name": "Pantoprazole", "dosage": "40 mg", "frequency": "Once daily", "purpose": "Gastric protection"}
        ]
    },
    "Respiratory": {
        "diagnosis_detail": "Acute respiratory compromise with oxygenation support and airway observation.",
        "medications": [
            {"name": "Salbutamol Neb", "dosage": "2.5 mg", "frequency": "Every 6 hours", "purpose": "Bronchodilation"},
            {"name": "Budesonide Neb", "dosage": "0.5 mg", "frequency": "Twice daily", "purpose": "Airway inflammation control"},
            {"name": "Azithromycin", "dosage": "500 mg", "frequency": "Once daily", "purpose": "Infection coverage"}
        ]
    }
}

COMMON_VISUALIZATION_TEMPLATE = {
    "timeline_labels": ["D-3", "D-2", "D-1", "D0", "D+1"],
    "breakdown_labels": ["Primary", "Secondary", "Observation"]
}


def build_patient_history(record):
    condition_data = CONDITION_DETAILS.get(record["condition"], {
        "diagnosis_detail": "Clinical diagnosis under active review.",
        "medications": []
    })

    baseline_response = max(record["response_time"] - 2, 1)
    timeline_days = COMMON_VISUALIZATION_TEMPLATE["timeline_labels"]
    response_timeline = [
        baseline_response + 2,
        baseline_response + 1,
        baseline_response + 1,
        record["response_time"],
        max(record["response_time"] - 1, 1)
    ]
    accuracy_timeline = [
        max(record["accuracy"] - 6, 70),
        max(record["accuracy"] - 4, 72),
        max(record["accuracy"] - 2, 74),
        record["accuracy"],
        min(record["accuracy"] + 1, 99)
    ]

    vitals = [
        {"time": "T-30 min", "heart_rate": 108, "spo2": 93, "blood_pressure": "148/92", "temperature": "99.1°F"},
        {"time": "T-20 min", "heart_rate": 102, "spo2": 94, "blood_pressure": "142/88", "temperature": "99.0°F"},
        {"time": "T-10 min", "heart_rate": 98, "spo2": 95, "blood_pressure": "136/84", "temperature": "98.8°F"},
        {"time": "Current", "heart_rate": 94, "spo2": 97, "blood_pressure": "130/82", "temperature": "98.6°F"}
    ]

    event_log = [
        {"event": "Emergency intake completed", "status": "Completed"},
        {"event": "AI triage and risk scoring", "status": "Completed"},
        {"event": "Primary intervention initiated", "status": "Completed"},
        {"event": "Medication protocol active", "status": "Ongoing" if record["status"] == "Ongoing" else "Completed"},
        {"event": "Recovery monitoring", "status": record["status"]}
    ]

    return {
        "patient_id": record["patient_id"],
        "name": record["name"],
        "date": record["date"],
        "condition": record["condition"],
        "status": record["status"],
        "prediction_accuracy": record["accuracy"],
        "response_time": record["response_time"],
        "patient_summary": {
            "age": 40 + (int(record["patient_id"].split("-")[-1]) % 16),
            "blood_group": ["A+", "B+", "O+", "AB+"][int(record["patient_id"].split("-")[-1]) % 4],
            "emergency_contact": "+1-555-010" + record["patient_id"].split("-")[-1],
            "attending_doctor": "Dr. Priya Menon",
            "ambulance_unit": "Unit-" + record["patient_id"].split("-")[-1],
            "diagnosis_detail": condition_data["diagnosis_detail"]
        },
        "medications": condition_data["medications"],
        "vitals": vitals,
        "event_log": event_log,
        "chart_data": {
            "labels": timeline_days,
            "response_timeline": response_timeline,
            "accuracy_timeline": accuracy_timeline,
            "condition_breakdown": {
                "labels": COMMON_VISUALIZATION_TEMPLATE["breakdown_labels"],
                "values": [60, 25, 15]
            }
        }
    }


def init_patient_database():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    with get_db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS patient_histories (
                patient_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                date TEXT NOT NULL,
                condition TEXT NOT NULL,
                status TEXT NOT NULL,
                accuracy INTEGER NOT NULL,
                response_time INTEGER NOT NULL,
                patient_summary_json TEXT NOT NULL,
                medications_json TEXT NOT NULL,
                vitals_json TEXT NOT NULL,
                event_log_json TEXT NOT NULL,
                visualization_json TEXT NOT NULL
            )
            """
        )

        existing_count = connection.execute("SELECT COUNT(*) AS count FROM patient_histories").fetchone()["count"]
        if existing_count == 0:
            for record in HISTORICAL_PATIENT_RECORDS:
                history = build_patient_history(record)
                connection.execute(
                    """
                    INSERT INTO patient_histories (
                        patient_id, name, date, condition, status, accuracy, response_time,
                        patient_summary_json, medications_json, vitals_json, event_log_json, visualization_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        history["patient_id"],
                        history["name"],
                        history["date"],
                        history["condition"],
                        history["status"],
                        history["prediction_accuracy"],
                        history["response_time"],
                        json.dumps(history["patient_summary"]),
                        json.dumps(history["medications"]),
                        json.dumps(history["vitals"]),
                        json.dumps(history["event_log"]),
                        json.dumps(history["chart_data"])
                    )
                )
        connection.commit()


def fetch_all_patient_records():
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT patient_id, name, date, condition, accuracy, response_time, status
            FROM patient_histories
            ORDER BY date DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_patient_history(patient_id):
    with get_db_connection() as connection:
        row = connection.execute(
            """
            SELECT patient_id, name, date, condition, status, accuracy, response_time,
                   patient_summary_json, medications_json, vitals_json, event_log_json, visualization_json
            FROM patient_histories
            WHERE patient_id = ?
            """,
            (patient_id,)
        ).fetchone()

    if not row:
        return None

    return {
        "patient_id": row["patient_id"],
        "name": row["name"],
        "date": row["date"],
        "condition": row["condition"],
        "status": row["status"],
        "prediction_accuracy": row["accuracy"],
        "response_time": row["response_time"],
        "patient_summary": json.loads(row["patient_summary_json"]),
        "medications": json.loads(row["medications_json"]),
        "vitals": json.loads(row["vitals_json"]),
        "event_log": json.loads(row["event_log_json"]),
        "chart_data": json.loads(row["visualization_json"])
    }


init_patient_database()

# Initialize sensors ONCE (important)
hr_sensor = HeartRateSensor()
spo2_sensor = SpO2Sensor()
temp_sensor = TemperatureSensor()
resp_sensor = RespirationSensor()
bp_sensor = BloodPressureSensor()
ecg_sensor = ECGSensor()
camera_analysis_lock = threading.Lock()
camera_analysis_engine = None

if initialize_camera_dependencies():
    camera_analysis_engine = CameraAnalysisEngine(
        report_path=CAMERA_REPORT_PATH,
        observation_time=60
    )


class LiveCameraService:
    def __init__(self, analysis_engine, analysis_lock, camera_index=0):
        self.analysis_engine = analysis_engine
        self.analysis_lock = analysis_lock
        self.camera_index = camera_index
        self.thread = None
        self.running = False
        self.latest_jpeg = None
        self.frame_ready = threading.Condition()
        self.thread_guard = threading.Lock()

    def start(self):
        if self.analysis_engine is None or cv2 is None:
            return

        with self.thread_guard:
            if self.running and self.thread and self.thread.is_alive():
                return

            self.running = True
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()

    def _capture_loop(self):
        camera = cv2.VideoCapture(self.camera_index)

        if not camera.isOpened():
            with self.frame_ready:
                self.latest_jpeg = None
                self.frame_ready.notify_all()
            self.running = False
            return

        try:
            while self.running:
                success, frame = camera.read()
                if not success:
                    time.sleep(0.02)
                    continue

                with self.analysis_lock:
                    analyzed_frame = self.analysis_engine.process_frame(frame)

                encoded, buffer = cv2.imencode('.jpg', analyzed_frame)
                if not encoded:
                    continue

                with self.frame_ready:
                    self.latest_jpeg = buffer.tobytes()
                    self.frame_ready.notify_all()
        finally:
            camera.release()
            self.running = False

    def get_frame(self, timeout=2.0):
        self.start()
        with self.frame_ready:
            if self.latest_jpeg is None:
                self.frame_ready.wait(timeout=timeout)
            return self.latest_jpeg


live_camera_service = LiveCameraService(
    analysis_engine=camera_analysis_engine,
    analysis_lock=camera_analysis_lock,
    camera_index=0
)

EXTERNAL_ECG_URL = "https://iotwebserver.in/ECG.php"
ECG_SERIES_LIMIT = 100
ecg_series_lock = threading.Lock()
ecg_series_history = []


def _to_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_numeric_from_payload(payload):
    if isinstance(payload, (int, float)):
        return float(payload)

    if isinstance(payload, list):
        for item in reversed(payload):
            candidate = _extract_numeric_from_payload(item)
            if candidate is not None:
                return candidate
        return None

    if isinstance(payload, dict):
        for key in ("ecg", "ecg_value", "value", "signal", "reading", "data"):
            if key in payload:
                candidate = _extract_numeric_from_payload(payload.get(key))
                if candidate is not None:
                    return candidate

        for value in payload.values():
            candidate = _extract_numeric_from_payload(value)
            if candidate is not None:
                return candidate
        return None

    if isinstance(payload, str):
        matches = re.findall(r"-?\d+(?:\.\d+)?", payload)
        if not matches:
            return None
        return _to_float(matches[-1])

    return None


def fetch_external_ecg_sample():
    try:
        with urlopen(EXTERNAL_ECG_URL, timeout=3) as response:
            body = response.read().decode("utf-8", errors="ignore").strip()
    except (URLError, TimeoutError, OSError):
        return None

    if not body:
        return None

    try:
        parsed = json.loads(body)
        value = _extract_numeric_from_payload(parsed)
        if value is not None:
            return value
    except json.JSONDecodeError:
        pass

    return _extract_numeric_from_payload(body)

def get_live_sensors(force_resp_refresh=False):
    data = esp32.read_packet(force_resp_refresh=force_resp_refresh)
    resp_status = data.get("resp_status", "Unknown")
    resp_display = f"{data['resp_rate']} RR"
    if resp_status in ("Normal", "Abnormal"):
        resp_display = f"{resp_display} ({resp_status})"

    return {
        "heart_rate": f"{data['heart_rate']} BPM",
        "spo2": f"{data['spo2']}%",
        "ecg_status": data["ecg_status"].replace("_", " ").title(),
        "temp": f"{data['temp']}°F",
        "resp_rate": resp_display,
        "blood_pressure": f"{data['blood_pressure']['sys']}/{data['blood_pressure']['dia']} mmHg"
    }


def is_anonymous_mode_active():
    toggle_value = str(request.args.get("anonymous", "0")).strip().lower()
    return toggle_value in ("1", "true", "yes", "on")


def resolve_patient_context():
    anonymous_mode = is_anonymous_mode_active()
    patient = dict(PATIENT_RECORDS[0])
    if anonymous_mode:
        patient.update({
            "id": "UNKNOWN",
            "name": "Unknown Patient",
            "dob": "Unknown",
            "age": "Unknown",
            "past_conditions": "Unknown",
            "allergies": "Unknown"
        })
    return patient, anonymous_mode


# ----------------------------
# Dashboard Route
# ----------------------------
@app.route('/')
def index():
    patient, anonymous_mode = resolve_patient_context()
    sensors = get_live_sensors(force_resp_refresh=True)

    # ML decides WHAT
    ml_result = predict_risk_ml(sensors, patient, anonymous_mode=anonymous_mode)

    # Rules decide WHY + ACTIONS
    rule_result = evaluate_risk(sensors, patient, anonymous_mode=anonymous_mode)

    # Camera summary (SAFE)
    camera_report = load_camera_report() or {
        "bleeding_risk": "Pending",
        "movement_risk": "Pending",
        "posture_risk": "Pending",
        "overall_risk": "Pending",
        "summary": ["Camera analysis not yet completed."]
    }
    camera_report["diagnosis"] = build_combined_diagnosis(camera_report, sensors, anonymous_mode=anonymous_mode)

    return render_template(
        'dashboard.html',
        patient=patient,
        anonymous_mode=anonymous_mode,
        sensors=sensors,
        ai={
            "primary_risk": ml_result["ml_risk"],
            "risk_level": rule_result["risk_level"],
            "confidence": ml_result["confidence"],
            "indicators": rule_result["indicators"],
            "explanations": rule_result["explanations"],
            "recommendations": rule_result["recommendations"],
            "external_summary": rule_result["external_summary"],
            "internal_summary": rule_result["internal_summary"]
        },
        camera=camera_report
    )


@app.route('/analysis')
def analysis_page():
    patient, anonymous_mode = resolve_patient_context()
    sensors = get_live_sensors(force_resp_refresh=True)

    ml_result = predict_risk_ml(sensors, patient, anonymous_mode=anonymous_mode)
    rule_result = evaluate_risk(sensors, patient, anonymous_mode=anonymous_mode)

    camera_report = load_camera_report() or {
        "bleeding_risk": "Pending",
        "movement_risk": "Pending",
        "posture_risk": "Pending",
        "overall_risk": "Pending",
        "summary": ["Camera analysis not yet completed."]
    }
    camera_report["diagnosis"] = build_combined_diagnosis(camera_report, sensors, anonymous_mode=anonymous_mode)

    return render_template(
        'analysis.html',
        patient=patient,
        anonymous_mode=anonymous_mode,
        sensors=sensors,
        ai={
            "primary_risk": ml_result["ml_risk"],
            "risk_level": rule_result["risk_level"],
            "confidence": ml_result["confidence"],
            "indicators": rule_result["indicators"],
            "explanations": rule_result["explanations"],
            "recommendations": rule_result["recommendations"],
            "external_summary": rule_result["external_summary"],
            "internal_summary": rule_result["internal_summary"]
        },
        camera=camera_report
    )


@app.route('/camera-feed')
def camera_feed():
    if live_camera_service.analysis_engine is None or cv2 is None:
        return Response(
            "Camera service unavailable. Check OpenCV/Numpy environment and restart.",
            status=503,
            mimetype='text/plain'
        )

    def generate_frames():
        while True:
            frame_bytes = live_camera_service.get_frame(timeout=2.0)
            if not frame_bytes:
                continue

            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
            )

    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/camera-analysis')
def camera_analysis_data():
    camera_report = load_camera_report() or {
        "bleeding_risk": "Pending",
        "movement_risk": "Pending",
        "posture_risk": "Pending",
        "overall_risk": "Pending",
        "summary": ["Camera analysis in progress."]
    }
    return jsonify(camera_report)


@app.route('/live-sensors')
def live_sensors_data():
    return jsonify(get_live_sensors())


@app.route('/ecg-data')
def ecg_data():
    sample = fetch_external_ecg_sample()

    with ecg_series_lock:
        if sample is not None:
            ecg_series_history.append(sample)

        if not ecg_series_history:
            ecg_series_history.extend([0.0] * ECG_SERIES_LIMIT)

        if len(ecg_series_history) > ECG_SERIES_LIMIT:
            del ecg_series_history[:-ECG_SERIES_LIMIT]

        series_snapshot = list(ecg_series_history)

    labels = list(range(len(series_snapshot)))
    return jsonify({
        "source": EXTERNAL_ECG_URL,
        "value": sample,
        "labels": labels,
        "series": series_snapshot
    })


@app.route('/combined-diagnosis')
def combined_diagnosis_data():
    sensors = get_live_sensors()
    anonymous_mode = is_anonymous_mode_active()
    camera_report = load_camera_report() or {
        "bleeding_risk": "Pending",
        "movement_risk": "Pending",
        "posture_risk": "Pending",
        "overall_risk": "Pending",
        "summary": ["Camera analysis in progress."]
    }

    diagnosis = build_combined_diagnosis(camera_report, sensors, anonymous_mode=anonymous_mode)
    return jsonify({
        "diagnosis": diagnosis,
        "camera": {
            "bleeding_risk": camera_report.get("bleeding_risk", "Pending"),
            "movement_risk": camera_report.get("movement_risk", "Pending"),
            "posture_risk": camera_report.get("posture_risk", "Pending"),
            "overall_risk": camera_report.get("overall_risk", "Pending"),
            "summary": camera_report.get("summary", [])
        },
        "sensors": sensors
    })


@app.route('/camera-analysis-status')
def camera_analysis_status():
    if camera_analysis_engine is None:
        return jsonify({
            "phase": "unavailable",
            "remaining_seconds": 0,
            "bleeding_risk": "Pending",
            "movement_risk": "Pending",
            "posture_risk": "Pending",
            "message": "Camera dependencies not loaded",
            "error": CAMERA_IMPORT_ERROR
        })

    with camera_analysis_lock:
        status = camera_analysis_engine.get_runtime_status()
    return jsonify(status)

# ----------------------------
# Patient Records Route
# ----------------------------
@app.route('/records')
def patient_records():
    patient_rows = fetch_all_patient_records()

    # Calculate analytics metrics
    total_patients = len(patient_rows)
    avg_accuracy = sum(r["accuracy"] for r in patient_rows) / total_patients if total_patients > 0 else 0
    prediction_success = round(avg_accuracy)
    avg_response_time = sum(r["response_time"] for r in patient_rows) / total_patients if total_patients > 0 else 0
    
    return render_template(
        'patient_records.html',
        patient_records=patient_rows,
        total_patients=total_patients,
        prediction_success=prediction_success,
        avg_accuracy=round(avg_accuracy),
        avg_response_time=f"{avg_response_time:.1f}"
    )


@app.route('/records/<patient_id>/history')
def patient_full_history(patient_id):
    history = fetch_patient_history(patient_id)
    if history is None:
        abort(404)

    return render_template('patient_history.html', history=history)

# ----------------------------
# Doctor Summary Route
# ----------------------------
@app.route('/doctor-summary')
def doctor_summary():
    patient, anonymous_mode = resolve_patient_context()
    sensors = get_live_sensors()

    ml_result = predict_risk_ml(sensors, patient, anonymous_mode=anonymous_mode)
    rule_result = evaluate_risk(sensors, patient, anonymous_mode=anonymous_mode)
    camera_report = load_camera_report() or {
        "bleeding_risk": "Pending",
        "movement_risk": "Pending",
        "posture_risk": "Pending",
        "overall_risk": "Pending",
        "summary": ["Camera analysis not yet completed."]
    }
    camera_report["diagnosis"] = build_combined_diagnosis(camera_report, sensors, anonymous_mode=anonymous_mode)

    return render_template(
        'doctor_summary.html',
        patient=patient,
        anonymous_mode=anonymous_mode,
        sensors=sensors,
        ai={
            "explanations": rule_result["explanations"],
            "recommendations": rule_result["recommendations"],
            "external_summary": rule_result["external_summary"],
            "internal_summary": rule_result["internal_summary"]
        },
        camera=camera_report
    )

# ----------------------------
# Run App
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True)
