# Historical Patient Records - Integration Guide

## Overview

The Historical Records system automatically captures completed patient cases for analytics, reporting, and performance tracking. This feature integrates seamlessly with your existing database to maintain a complete history of all patient admissions and outcomes.

## What Gets Stored in Historical Records

```
- Patient Name & ID
- Admission Date & Time
- Chief Complaint/Condition
- Diagnosis from AI analysis
- Treatment Outcome (Recovered, Recovering, Ongoing)
- System Accuracy Score
- Response Time (minutes)
- Status (Recovered, Ongoing, etc.)
- Notes & Additional Details
```

## Available API Endpoints

### Create/Update Historical Record
```
POST /api/historical-records
```
Request body:
```json
{
  "patient_id": "PAT-001",
  "entry_id": "ENT-001",
  "name": "John Doe",
  "date": "2026-03-31T14:23:45",
  "condition": "Chest Pain",
  "accuracy": 92,
  "response_time": 4,
  "status": "Recovered",
  "diagnosis": "Acute Coronary Syndrome",
  "outcome": "Recovered",
  "notes": "Treated successfully with aspirin and nitrates"
}
```

### Get All Historical Records
```
GET /api/historical-records?limit=50
```

### Get Patient's Historical Records
```
GET /api/patients/<patient_id>/historical
```

### Sync Active Entry to Historical
```
POST /api/entries/<entry_id>/sync-historical
```
Request body:
```json
{
  "status": "Recovered",
  "accuracy": 92,
  "response_time": 4,
  "notes": "Optional notes"
}
```

### Get Historical Analytics
```
GET /api/historical-analytics?days=30
```

Response includes:
```json
{
  "total_records": 45,
  "avg_accuracy": 89.5,
  "avg_response_time": 4.8,
  "status_breakdown": {
    "Recovered": 40,
    "Ongoing": 3,
    "Recovering": 2
  },
  "top_conditions": [
    {"condition": "Cardiac Arrest", "count": 12},
    {"condition": "Stroke", "count": 8}
  ]
}
```

## Helper Functions

### 1. Sync Entry to History
Mark a patient case as completed and add to historical records.

```python
from utils import sync_entry_to_history

# When case is completed
record_id = sync_entry_to_history(
    entry_id="ENT-001",
    status="Recovered",
    accuracy=92,
    response_time=4
)
```

### 2. Add Custom Historical Record
Manually add a patient to historical records.

```python
from utils import add_to_historical_records

record_id = add_to_historical_records(
    patient_id="PAT-001",
    entry_id="ENT-001",
    record_data={
        "accuracy": 94,
        "response_time": 3,
        "status": "Recovered",
        "diagnosis": "Myocardial Infarction",
        "notes": "Excellent response time"
    }
)
```

### 3. Get Analytics
Retrieve performance analytics from historical data.

```python
from utils import get_historical_analytics

# Get 30-day analytics
analytics = get_historical_analytics(days=30)

print(f"Total cases: {analytics['total_records']}")
print(f"Avg accuracy: {analytics['avg_accuracy']}%")
print(f"Avg response: {analytics['avg_response_time']} min")
print(f"Success rate: {analytics['status_breakdown']}")
```

## Integration Examples

### Example 1: Mark Case as Completed

```python
@app.route('/api/case-completed/<entry_id>', methods=['POST'])
def mark_case_completed(entry_id):
    """Mark a patient case as completed and move to history"""
    data = request.get_json()
    
    # Sync entry to historical records
    record_id = sync_entry_to_history(
        entry_id,
        status=data.get('status', 'Recovered'),
        accuracy=data.get('accuracy', 85),
        response_time=data.get('response_time', 5)
    )
    
    if record_id:
        save_event(
            data['patient_id'],
            entry_id,
            "Case Completed",
            f"Case marked as {data.get('status', 'Recovered')}"
        )
        
        return jsonify({
            "success": True,
            "record_id": record_id,
            "message": "Case added to history"
        }), 201
    
    return jsonify({"success": False, "error": "Entry not found"}), 404
```

### Example 2: Dashboard with Historical Analytics

```python
@app.route('/api/dashboard/analytics')
def get_analytics_dashboard():
    """Get comprehensive analytics for dashboard"""
    
    # Get current statistics
    patients_today = patient_db.get_patients_today()
    recent_entries = patient_db.get_recent_patient_summary(limit=10)
    
    # Get historical analytics
    analytics_30day = get_historical_analytics(days=30)
    analytics_90day = get_historical_analytics(days=90)
    
    return jsonify({
        "success": True,
        "current": {
            "patients_today": patients_today,
            "recent_entries": recent_entries
        },
        "historical_30day": analytics_30day,
        "historical_90day": analytics_90day,
        "timestamp": datetime.now().isoformat()
    }), 200
```

### Example 3: Auto-sync Discharged Patients

```python
@app.route('/api/discharge-patient/<entry_id>', methods=['POST'])
def discharge_patient(entry_id):
    """Discharge a patient and add to historical records"""
    data = request.get_json()
    
    # Get entry details
    conn = patient_db.get_connection()
    entry = conn.execute(
        "SELECT patient_id FROM patient_entries WHERE entry_id = ?",
        (entry_id,)
    ).fetchone()
    conn.close()
    
    if not entry:
        return jsonify({"error": "Entry not found"}), 404
    
    patient_id = entry["patient_id"]
    
    # Get latest analysis to extract accuracy
    analysis = patient_db.get_latest_analysis(entry_id)
    accuracy = analysis.get('confidence', 85) if analysis else 85
    
    # Sync to historical
    sync_entry_to_history(
        entry_id,
        status=data.get('outcome_status', 'Recovered'),
        accuracy=accuracy,
        response_time=data.get('response_time', 5)
    )
    
    # Update entry status
    patient_db.update_entry_status(entry_id, "Discharged")
    
    # Log event
    save_event(patient_id, entry_id, "Discharge", "Patient discharged to hospital/home")
    
    return jsonify({
        "success": True,
        "message": "Patient discharged and added to history"
    }), 200
```

### Example 4: Retrieve Historical Records for Reporting

```python
@app.route('/api/reports/patient-history/<patient_id>')
def patient_history_report(patient_id):
    """Generate patient history report"""
    
    # Get patient
    patient = patient_db.get_patient(patient_id)
    if not patient:
        return jsonify({"error": "Patient not found"}), 404
    
    # Get all entries
    entries = patient_db.get_patient_entries(patient_id)
    
    # Get historical records
    historical = patient_db.get_patient_historical_records(patient_id)
    
    return jsonify({
        "success": True,
        "patient": {
            "name": patient['name'],
            "age": patient['age'],
            "contact": patient['phone']
        },
        "total_admissions": len(entries),
        "historical_records": historical,
        "timestamp": datetime.now().isoformat()
    }), 200
```

## Database Schema

### historical_records Table

```sql
CREATE TABLE historical_records (
    record_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    entry_id TEXT,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    condition TEXT,
    accuracy INTEGER,
    response_time INTEGER,
    status TEXT,
    diagnosis TEXT,
    outcome TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY(entry_id) REFERENCES patient_entries(entry_id)
);
```

## Query Examples

### Get patients treated in last 24 hours

```python
records = patient_db.get_historical_records(limit=100)
recent = [r for r in records if 
         datetime.fromisoformat(r['date']) > 
         datetime.now() - timedelta(hours=24)]
```

### Get all cases with high accuracy

```python
all_records = patient_db.get_historical_records(limit=1000)
high_accuracy = [r for r in all_records if r['accuracy'] >= 90]
```

### Get success rate by condition

```python
records = patient_db.get_historical_records(limit=500)

by_condition = {}
for record in records:
    condition = record['condition']
    if condition not in by_condition:
        by_condition[condition] = {'total': 0, 'recovered': 0}
    
    by_condition[condition]['total'] += 1
    if record['status'] == 'Recovered':
        by_condition[condition]['recovered'] += 1

for condition, stats in by_condition.items():
    rate = (stats['recovered'] / stats['total']) * 100
    print(f"{condition}: {rate:.1f}% recovery rate")
```

## Workflow: Patient Admission to History

```
1. Patient Admitted
   ↓
   save_patient_admission()
   ↓
   patient_entries table

2. Vitals Recorded
   ↓
   save_vital_signs()
   ↓
   vital_readings table

3. AI Analysis Done
   ↓
   save_analysis_result()
   ↓
   analysis_results table

4. Case Completed / Patient Discharged
   ↓
   sync_entry_to_history() or add_to_historical_records()
   ↓
   historical_records table

5. Analytics & Reporting
   ↓
   Query historical_records table
   ↓
   Display on dashboard
```

## Best Practices

1. **Sync Immediately Upon Discharge**: Don't wait to add completed cases to history
2. **Accurate Accuracy Scores**: Use the AI confidence score as accuracy metric
3. **Consistent Status Values**: Use: Recovered, Recovering, Ongoing, Discharged
4. **Include Response Times**: Helps track ambulance performance
5. **Add Clinical Notes**: Include relevant treatment details in notes field
6. **Regular Analytics Review**: Check monthly/quarterly performance

## Querying Historical Data

### Most common query patterns

```python
# Top conditions
from db.models import patient_db

# Get analytics
analytics = patient_db.get_historical_analytics(days=90)

# Top conditions
print(analytics['top_conditions'])
# Output: [{'condition': 'Cardiac Arrest', 'count': 12}, ...]

# Status breakdown
print(analytics['status_breakdown'])
# Output: {'Recovered': 45, 'Ongoing': 2, 'Recovering': 3}

# Performance metrics
print(f"Avg Accuracy: {analytics['avg_accuracy']}%")
print(f"Avg Response: {analytics['avg_response_time']} min")
```

## Testing Historical Records

Run the test suite to verify historical records functionality:

```bash
python test_database.py
```

Tests include:
- ✓ Creating historical records
- ✓ Getting historical records
- ✓ Syncing entries to history
- ✓ Analytics calculations
- ✓ Status breakdowns
- ✓ Top conditions analysis

## Troubleshooting

### Records not appearing in history

1. Check that entry exists in database
2. Verify patient_id and entry_id are correct
3. Ensure sync function was called
4. Check database file exists at `data/patients.db`

### Analytics returning zero values

1. Ensure historical records have been added
2. Check that accuracy/response_time fields are populated
3. Verify date range is correct
4. Run test_database.py to populate test data

## Next Steps

1. ✅ Integrate sync-to-history endpoints in discharge routes
2. ✅ Display historical analytics on admin dashboard
3. ✅ Generate monthly performance reports
4. ✅ Track trends over time
5. ✅ Analyze by condition, ambulance unit, paramedic

## Summary

| Feature | Method | Returns |
|---------|--------|---------|
| Add to history | `add_to_historical_records()` | record_id |
| Sync entry | `sync_entry_to_history()` | record_id |
| Get analytics | `get_historical_analytics()` | dict with stats |
| List records | `get_historical_records()` | list of records |
| List by patient | `get_patient_historical_records()` | list of records |

---

**Historical records provide complete audit trail and performance metrics for your ambulance system!**
