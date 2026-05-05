# Quick Integration Steps for app.py

## Step 1: Add Imports (at the top of app.py)

Add these import lines after your existing imports:

```python
# Database imports
from db.models import patient_db
from api.routes import register_patient_routes
from utils import (
    save_patient_admission,
    save_vital_signs,
    save_analysis_result,
    save_event,
    get_patient_complete_record
)
```

## Step 2: Register API Routes (after Flask app creation)

After your Flask app is created, register the new routes:

```python
app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ... your existing Flask configuration ...

# Register patient database API routes
register_patient_routes(app)
```

## Step 3: Modify Dashboard Route to Save Data

Update your existing `/` route to save data when processing patients:

```python
@app.route('/')
def index():
    patient, anonymous_mode = resolve_patient_context()
    sensors = get_live_sensors()

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

    # ===== NEW: Save data to database =====
    try:
        # Save patient if new
        patient_db.get_patient(patient["id"]) or patient_db.add_patient({
            "patient_id": patient["id"],
            "name": patient["name"],
            "age": patient.get("age"),
            "past_conditions": patient.get("past_conditions"),
            "allergies": patient.get("allergies")
        })
        
        # Save vital readings (optional, can be called separately)
        # save_vital_signs(patient["id"], None, sensors)
        
    except Exception as e:
        print(f"Database save error: {e}")
    # ===== END NEW =====

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
```

## Step 4: Add New Route for Patient Admission

Add this new route to handle patient admissions:

```python
@app.route('/api/patient-admission', methods=['POST'])
def patient_admission():
    """Handle patient admission and save to database"""
    try:
        data = request.get_json()
        patient_info = data.get('patient', {})
        sensors_data = data.get('sensors', {})
        ai_results = data.get('ai_results', {})
        camera_report = data.get('camera_report', {})
        
        # Save admission
        entry_id = save_patient_admission(
            patient_info,
            ambulance_unit=data.get('ambulance_unit'),
            paramedic_name=data.get('paramedic_name')
        )
        patient_id = patient_info.get('id')
        
        # Save vital signs
        reading_id = save_vital_signs(patient_id, entry_id, sensors_data)
        
        # Save analysis results
        analysis_id = save_analysis_result(patient_id, entry_id, ai_results, camera_report)
        
        # Log admission event
        save_event(patient_id, entry_id, "Emergency Admission", 
                   f"Patient {patient_info.get('name')} admitted via ambulance crew")
        
        return jsonify({
            "success": True,
            "entry_id": entry_id,
            "reading_id": reading_id,
            "analysis_id": analysis_id,
            "message": "Patient data saved to database"
        }), 201
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
```

## Step 5: Add Route to Get Recently Entered Data

Add this route to fetch recently entered patient data:

```python
@app.route('/dashboard/recent-patients')
def recent_patients():
    """Display recently entered patient data"""
    try:
        recent = patient_db.get_recent_patient_summary(limit=20)
        
        return render_template(
            'recent_patients.html',
            patients=recent,
            patients_today=patient_db.get_patients_today()
        )
    except Exception as e:
        return render_template(
            'recent_patients.html',
            patients=[],
            error=str(e)
        )
```

## Step 6: Add Route to Get Patient History

Add this route to view complete patient history:

```python
@app.route('/api/patient-record/<patient_id>')
def patient_record(patient_id):
    """Get complete patient record with all data"""
    try:
        record = get_patient_complete_record(patient_id)
        
        if not record:
            return jsonify({"success": False, "error": "Patient not found"}), 404
        
        return jsonify({
            "success": True,
            "patient": record["patient"],
            "entries": record["entries"],
            "vitals": record["vitals"],
            "analysis": record["analysis"],
            "events": record["events"]
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
```

## Step 7: Update Existing Patient History Route

If you have a `/patient-history` route, update it to use the database:

```python
@app.route('/patient-history/<patient_id>')
def patient_history(patient_id):
    """Get patient history from database"""
    try:
        # First check database
        record = get_patient_complete_record(patient_id)
        
        if record:
            return render_template(
                'patient_history.html',
                patient_id=patient_id,
                patient=record["patient"],
                entries=record["entries"],
                latest_vitals=record["vitals"][0] if record["vitals"] else None,
                latest_analysis=record["analysis"],
                events=record["events"]
            )
        else:
            # Fallback to existing method if not in database
            history = fetch_patient_history(patient_id)
            if history:
                return render_template('patient_history.html', history=history)
            else:
                return "Patient not found", 404
                
    except Exception as e:
        return f"Error: {str(e)}", 500
```

## Step 8: Add Continuous Monitoring Route

Add this route to periodically save vital signs during monitoring:

```python
@app.route('/api/monitor-vitals/<entry_id>', methods=['POST'])
def monitor_vitals(entry_id):
    """Update vital signs for an active entry"""
    try:
        # Get entry to find patient_id
        conn = patient_db.get_connection()
        entry = conn.execute(
            "SELECT patient_id FROM patient_entries WHERE entry_id = ?",
            (entry_id,)
        ).fetchone()
        conn.close()
        
        if not entry:
            return jsonify({"success": False, "error": "Entry not found"}), 404
        
        patient_id = entry["patient_id"]
        sensors = get_live_sensors()
        
        # Save latest vital reading
        reading_id = save_vital_signs(patient_id, entry_id, sensors)
        
        # Optional: Check if analysis needs update
        data = request.get_json() or {}
        if data.get('update_analysis'):
            ml_result = predict_risk_ml(sensors, {})
            rule_result = evaluate_risk(sensors, {})
            camera_report = load_camera_report()
            
            analysis_id = save_analysis_result(
                patient_id,
                entry_id,
                {**ml_result, **rule_result},
                camera_report
            )
            
            return jsonify({
                "success": True,
                "reading_id": reading_id,
                "analysis_id": analysis_id
            }), 200
        
        return jsonify({
            "success": True,
            "reading_id": reading_id
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
```

## Step 9: Add Dashboard API Route

Update your `/analysis` or create a `/api/dashboard/data` route:

```python
@app.route('/api/dashboard/data')
def dashboard_data():
    """Get dashboard statistics and recent data"""
    try:
        patients_today = patient_db.get_patients_today()
        recent_summary = patient_db.get_recent_patient_summary(limit=10)
        
        return jsonify({
            "success": True,
            "patients_today": patients_today,
            "recent_patients": recent_summary,
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
```

## Usage in Frontend/JavaScript

Example of calling the new endpoints from your frontend:

```javascript
// Admit a new patient
async function admitPatient(patientData, sensorsData, aiResults, cameraReport) {
    const response = await fetch('/api/patient-admission', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            patient: patientData,
            sensors: sensorsData,
            ai_results: aiResults,
            camera_report: cameraReport,
            ambulance_unit: 'Unit-01',
            paramedic_name: 'John Paramedic'
        })
    });
    const result = await response.json();
    return result.entry_id;
}

// Get recently entered patients
async function getRecentPatients() {
    const response = await fetch('/api/dashboard/recently-entered?limit=10');
    const data = await response.json();
    return data.data;
}

// Update vitals during monitoring
async function updateVitals(entryId) {
    const response = await fetch(`/api/monitor-vitals/${entryId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ update_analysis: true })
    });
    const result = await response.json();
    return result;
}

// Get patient complete record
async function getPatientRecord(patientId) {
    const response = await fetch(`/api/patient-record/${patientId}`);
    const data = await response.json();
    return data.patient;
}
```

## Summary of Changes

| File | Change | Impact |
|------|--------|--------|
| app.py | Add imports | Enable database access |
| app.py | Call register_patient_routes() | Enable 20+ API endpoints |
| app.py | Modify / route | Save patient data |
| app.py | Add /api/patient-admission | Handle admissions |
| app.py | Add /dashboard/recent-patients | Display recently entered |
| app.py | Add /api/patient-record/<id> | View patient history |
| app.py | Add /api/monitor-vitals/<id> | Continuous monitoring |
| app.py | Add /api/dashboard/data | Dashboard statistics |

## Testing the Integration

Test the database integration:

```bash
# Test creating a patient
curl -X POST http://localhost:5000/api/patients \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"PAT-001","name":"Test Patient","age":45}'

# Test getting recent entries
curl http://localhost:5000/api/entries/recent?limit=5

# Test dashboard summary
curl http://localhost:5000/api/dashboard/summary

# Test patient admission
curl -X POST http://localhost:5000/api/patient-admission \
  -H "Content-Type: application/json" \
  -d '{
    "patient": {"id":"PAT-001","name":"Test Patient","age":45},
    "sensors": {"heart_rate":"72 BPM","spo2":"98%","temp":"98.6°F"},
    "ai_results": {"ml_risk":"Low","risk_level":"Low","confidence":95}
  }'
```

## File Structure After Integration

```
ambulance_system/
├── app.py                                    (MODIFIED)
├── DATABASE_INTEGRATION_GUIDE.md             (NEW)
├── APP_INTEGRATION_STEPS.md                  (NEW - this file)
├── db/
│   ├── __init__.py
│   └── models.py
├── api/
│   ├── __init__.py
│   └── routes.py
├── utils/
│   ├── __init__.py
│   └── db_helpers.py
├── data/
│   └── patients.db                           (created automatically)
└── ... (rest of your files)
```

## Next: Update HTML Templates (Optional)

Create a new template `templates/recent_patients.html` to display recently entered data:

```html
{% extends "dashboard.html" %}

{% block content %}
<div class="recent-patients-container">
    <h2>Recently Entered Patients (Today: {{ patients_today }})</h2>
    <table class="patients-table">
        <thead>
            <tr>
                <th>Name</th>
                <th>Age</th>
                <th>Complaint</th>
                <th>Initial Condition</th>
                <th>Entry Time</th>
                <th>Latest HR</th>
                <th>Latest SpO2</th>
                <th>Risk Level</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
            {% for patient in patients %}
            <tr>
                <td><a href="/patient-history/{{ patient.patient_id }}">{{ patient.name }}</a></td>
                <td>{{ patient.age }}</td>
                <td>{{ patient.chief_complaint }}</td>
                <td>{{ patient.initial_condition }}</td>
                <td>{{ patient.entry_timestamp }}</td>
                <td>{{ patient.latest_hr or 'N/A' }}</td>
                <td>{{ patient.latest_spo2 or 'N/A' }}</td>
                <td><span class="risk-{{ patient.latest_risk|lower }}">{{ patient.latest_risk }}</span></td>
                <td>{{ patient.status }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

This completes the database integration!
