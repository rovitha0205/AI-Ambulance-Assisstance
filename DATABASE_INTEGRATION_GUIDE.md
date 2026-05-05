# Database System Integration Guide

## Overview

A complete SQLite-based database system has been added to store patient data including:
- Patient demographic information
- Admission/entry records
- Vital signs and sensor readings
- AI analysis results and diagnoses
- Patient events/actions
- Historical records

## Database Structure

### Table: `patients`
Stores patient demographics and medical history.

```sql
- patient_id (PRIMARY KEY)
- name, age, date_of_birth, gender
- blood_group, phone, email, address
- past_conditions, allergies
- emergency_contact, emergency_contact_phone
- created_at, updated_at
```

### Table: `patient_entries`
Stores admission/entry records when patients are admitted.

```sql
- entry_id (PRIMARY KEY)
- patient_id (FOREIGN KEY)
- entry_timestamp
- admission_type, chief_complaint, initial_condition
- ambulance_unit, paramedic_name, hospital_destination
- status, notes
- created_at
```

### Table: `vital_readings`
Stores sensor and vital signs data.

```sql
- reading_id (PRIMARY KEY)
- patient_id, entry_id (FOREIGN KEYS)
- heart_rate, spo2, temperature
- blood_pressure_sys, blood_pressure_dia
- respiration_rate, ecg_status
- reading_timestamp, created_at
```

### Table: `analysis_results`
Stores AI analysis and diagnosis results.

```sql
- analysis_id (PRIMARY KEY)
- patient_id, entry_id (FOREIGN KEYS)
- ml_risk_level, rule_engine_risk, overall_risk
- confidence, bleeding_risk, movement_risk, posture_risk
- diagnosis, recommended_condition
- medications_json
- analysis_timestamp, created_at
```

### Table: `patient_events`
Stores patient events and actions.

```sql
- event_id (PRIMARY KEY)
- patient_id, entry_id (FOREIGN KEYS)
- event_type, event_description, event_status
- event_timestamp, created_at
```

## Installation & Setup

### 1. Verify Directory Structure

Ensure these directories exist (created automatically):
```
ambulance_system/
├── db/
│   ├── __init__.py
│   └── models.py
├── api/
│   ├── __init__.py
│   └── routes.py
├── utils/
│   ├── __init__.py
│   └── db_helpers.py
└── app.py
```

### 2. Update `app.py`

Add these imports at the top of your `app.py`:

```python
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

### 3. Register API Routes

After creating your Flask app, register the routes:

```python
app = Flask(__name__)
# ... your existing Flask setup ...

# Register patient data API routes
register_patient_routes(app)
```

## Available API Endpoints

### Patient Management
```
POST /api/patients                      - Create new patient
GET  /api/patients                      - List all patients
GET  /api/patients/<patient_id>         - Get patient info
```

### Patient Entries (Admissions)
```
POST /api/entries                       - Create new entry
GET  /api/entries/recent                - Get recently entered data
GET  /api/patients/<patient_id>/entries - Get patient's entries
PUT  /api/entries/<entry_id>/status     - Update entry status
```

### Vital Signs
```
POST /api/vitals                            - Record vital reading
GET  /api/patients/<patient_id>/vitals      - Get patient's vitals
GET  /api/entries/<entry_id>/vitals         - Get entry's vitals
```

### Analysis Results
```
POST /api/analysis                          - Save analysis result
GET  /api/patients/<patient_id>/analysis    - Get patient's analysis
GET  /api/entries/<entry_id>/analysis       - Get entry's latest analysis
```

### Events
```
POST /api/events                        - Record event
GET  /api/entries/<entry_id>/events     - Get entry's events
```

### Dashboard & Reporting
```
GET  /api/dashboard/summary             - Get dashboard statistics
GET  /api/dashboard/recently-entered    - Get recently entered patients
```

## Usage Examples

### Example 1: Save a New Patient Admission with All Data

```python
@app.route('/api/new-admission', methods=['POST'])
def new_admission():
    data = request.get_json()
    
    # Step 1: Save admission
    patient_info = {
        "id": data.get("patient_id"),
        "name": data.get("name"),
        "age": data.get("age"),
        "dob": data.get("dob"),
        "past_conditions": data.get("conditions"),
        "allergies": data.get("allergies"),
        "chief_complaint": data.get("complaint")
    }
    
    entry_id = save_patient_admission(patient_info, ambulance_unit="Unit-01")
    patient_id = patient_info["id"]
    
    # Step 2: Get current sensor data and save vitals
    sensors = get_live_sensors()
    reading_id = save_vital_signs(patient_id, entry_id, sensors)
    
    # Step 3: Get AI analysis and save
    ml_result = predict_risk_ml(sensors, patient_info)
    rule_result = evaluate_risk(sensors, patient_info)
    camera_report = load_camera_report()
    
    analysis_id = save_analysis_result(
        patient_id,
        entry_id,
        {**ml_result, **rule_result},
        camera_report
    )
    
    # Step 4: Log admission event
    save_event(patient_id, entry_id, "Admission", f"Patient admitted")
    
    return jsonify({
        "success": True,
        "entry_id": entry_id,
        "reading_id": reading_id,
        "analysis_id": analysis_id
    }), 201
```

### Example 2: Update Vitals During Monitoring

```python
@app.route('/api/update-vitals/<entry_id>', methods=['POST'])
def update_vitals(entry_id):
    # Get entry to find patient_id
    entry = patient_db.get_db_connection().execute(
        "SELECT patient_id FROM patient_entries WHERE entry_id = ?",
        (entry_id,)
    ).fetchone()
    
    if not entry:
        return jsonify({"error": "Entry not found"}), 404
    
    patient_id = entry["patient_id"]
    sensors = get_live_sensors()
    
    # Save latest vital reading
    reading_id = save_vital_signs(patient_id, entry_id, sensors)
    
    # Check if vitals indicate change in condition
    ml_result = predict_risk_ml(sensors, {})
    if ml_result["ml_risk"] != "Low":
        save_event(patient_id, entry_id, "Risk Change", 
                   f"Risk level changed to {ml_result['ml_risk']}")
    
    return jsonify({
        "success": True,
        "reading_id": reading_id
    }), 200
```

### Example 3: Retrieve Patient's Recent Data

```python
@app.route('/api/patient-summary/<patient_id>')
def get_patient_summary(patient_id):
    record = get_patient_complete_record(patient_id)
    
    if not record:
        return jsonify({"error": "Patient not found"}), 404
    
    return jsonify({
        "success": True,
        "patient_name": record["patient"]["name"],
        "entries": record["entries"],
        "latest_vitals": record["vitals"][0] if record["vitals"] else None,
        "latest_analysis": record["analysis"],
        "recent_events": record["events"][:5]
    }), 200
```

### Example 4: Get Recently Entered Patient Data via Dashboard

```html
<!-- In your dashboard template -->
<script>
fetch('/api/dashboard/recently-entered?limit=10')
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      data.data.forEach(patient => {
        console.log(`${patient.name} - ${patient.chief_complaint}`);
        console.log(`Latest HR: ${patient.latest_hr}, SpO2: ${patient.latest_spo2}`);
        console.log(`Risk: ${patient.latest_risk}`);
      });
    }
  });
</script>
```

## Database Functions

### Patient Database Class

Located in `db/models.py`, the `PatientDatabase` class provides methods:

```python
# Patient operations
patient_db.add_patient(data)
patient_db.get_patient(patient_id)
patient_db.get_all_patients(limit=100)

# Entry operations
patient_db.add_patient_entry(data)
patient_db.get_patient_entries(patient_id, limit=50)
patient_db.get_recent_entries(limit=20)
patient_db.update_entry_status(entry_id, status)

# Vital operations
patient_db.add_vital_reading(data)
patient_db.get_patient_vital_readings(patient_id, limit=100)
patient_db.get_entry_vital_readings(entry_id)

# Analysis operations
patient_db.add_analysis_result(data)
patient_db.get_patient_analysis(patient_id, limit=50)
patient_db.get_latest_analysis(entry_id)

# Event operations
patient_db.add_event(data)
patient_db.get_entry_events(entry_id)

# Statistics
patient_db.get_patients_today()
patient_db.get_recent_patient_summary(limit=10)
patient_db.cleanup_old_data(days=90)
```

## Helper Functions

Located in `utils/db_helpers.py`:

```python
# High-level convenience functions
save_patient_admission(patient_info, ambulance_unit, paramedic_name)
save_vital_signs(patient_id, entry_id, sensors_data)
save_analysis_result(patient_id, entry_id, ai_results, camera_report)
save_event(patient_id, entry_id, event_type, description, status)
get_patient_complete_record(patient_id, entry_id)
```

## Data Flow

```
Patient Admission
    ↓
save_patient_admission()
    ↓
┌─────────────────────────────┐
│ patients (demographics)     │
│ patient_entries (admission) │
└─────────────────────────────┘
    ↓
Continuous Monitoring
    ↓
save_vital_signs()
    ↓
┌──────────────────────────┐
│ vital_readings (sensors) │
└──────────────────────────┘
    ↓
AI Analysis
    ↓
save_analysis_result()
    ↓
┌────────────────────────────┐
│ analysis_results (AI risk) │
└────────────────────────────┘
    ↓
Event Logging
    ↓
save_event()
    ↓
┌─────────────────────┐
│ patient_events      │
└─────────────────────┘
```

## Querying Examples

### Get all vitals for a patient in the last 24 hours

```python
patient_id = "PAT-001"
vitals = patient_db.get_patient_vital_readings(patient_id)
recent_vitals = [v for v in vitals 
                 if datetime.fromisoformat(v['reading_timestamp']) 
                 > datetime.now() - timedelta(hours=24)]
```

### Get patients with high risk in last entry

```python
recent = patient_db.get_recent_patient_summary(limit=50)
high_risk_patients = [p for p in recent if p['latest_risk'] == 'High']
```

### Export patient data to JSON

```python
import json
record = get_patient_complete_record("PAT-001")
with open("patient_export.json", "w") as f:
    json.dump(record, f, indent=2, default=str)
```

## Important Notes

1. **Database Location**: Database file is stored at `data/patients.db`
2. **Timestamps**: All timestamps use ISO format (YYYY-MM-DDTHH:MM:SS.mmmmm)
3. **Foreign Keys**: Enable better data integrity
4. **Cleanup**: Use `patient_db.cleanup_old_data(days=90)` to remove old data
5. **Concurrent Access**: SQLite handles multiple reads but queues writes

## Troubleshooting

### Database file not created
- Ensure `data/` directory exists and has write permissions
- Check that `patient_db.initialize_database()` is called

### Import errors
- Verify all modules are in place: `db/`, `api/`, `utils/`
- Check that `__init__.py` files exist in all packages

### Foreign key constraints
- SQLite foreign keys are enabled by default
- Ensure patient_id exists before adding entries

## Next Steps

1. ✅ Import the modules in `app.py`
2. ✅ Register the API routes
3. ✅ Update your dashboard routes to use `save_patient_admission()` and related helpers
4. ✅ Update your analysis routes to call `save_analysis_result()`
5. ✅ Add monitoring routes to call `save_vital_signs()` periodically
6. ✅ Create a recent patients view using `/api/dashboard/recently-entered`

## Support

For questions or issues with the database system, refer to:
- [db/models.py](../db/models.py) - Complete database schema and operations
- [api/routes.py](../api/routes.py) - All API endpoints
- [utils/db_helpers.py](../utils/db_helpers.py) - Integration helpers
