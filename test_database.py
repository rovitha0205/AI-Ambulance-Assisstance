"""
Database System Test & Demo Script
Run this to verify the database is working correctly
"""

from db.models import patient_db
from utils import (
    save_patient_admission,
    save_vital_signs,
    save_analysis_result,
    save_event,
    get_patient_complete_record,
    add_to_historical_records,
    get_historical_analytics,
    sync_entry_to_history
)
from datetime import datetime, timedelta
import json


def print_section(title):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}\n")


def test_add_patient():
    """Test adding a patient"""
    print_section("TEST 1: Adding Patient")
    
    patient_data = {
        "patient_id": "TEST-PAT-001",
        "name": "John Doe",
        "age": 45,
        "gender": "Male",
        "blood_group": "O+",
        "phone": "555-1234",
        "past_conditions": "Hypertension, Type 2 Diabetes",
        "allergies": "Penicillin, Peanuts",
        "emergency_contact": "Jane Doe",
        "emergency_contact_phone": "555-5678"
    }
    
    patient_id = patient_db.add_patient(patient_data)
    print(f"✓ Patient added successfully")
    print(f"  Patient ID: {patient_id}")
    
    retrieved = patient_db.get_patient(patient_id)
    if retrieved:
        print(f"✓ Patient retrieved successfully")
        print(f"  Name: {retrieved['name']}")
        print(f"  Age: {retrieved['age']}")
        print(f"  Conditions: {retrieved['past_conditions']}")
    
    return patient_id


def test_patient_admission(patient_id):
    """Test creating a patient entry/admission"""
    print_section("TEST 2: Creating Patient Entry (Admission)")
    
    entry_data = {
        "patient_id": patient_id,
        "admission_type": "Emergency",
        "chief_complaint": "Chest pain and shortness of breath",
        "initial_condition": "Acute Chest Pain with Dyspnea",
        "ambulance_unit": "Unit-01",
        "paramedic_name": "Dr. Smith",
        "hospital_destination": "City General Hospital",
        "notes": "Patient transported from home, vitals initially unstable"
    }
    
    entry_id = patient_db.add_patient_entry(entry_data)
    print(f"✓ Patient entry created successfully")
    print(f"  Entry ID: {entry_id}")
    
    # Retrieve entries
    entries = patient_db.get_patient_entries(patient_id)
    print(f"✓ Retrieved {len(entries)} entry(ies)")
    if entries:
        print(f"  Latest entry: {entries[0]['entry_id']}")
        print(f"  Chief complaint: {entries[0]['chief_complaint']}")
    
    return entry_id


def test_vital_signs(patient_id, entry_id):
    """Test recording vital signs"""
    print_section("TEST 3: Recording Vital Signs")
    
    vital_readings = [
        {
            "patient_id": patient_id,
            "entry_id": entry_id,
            "heart_rate": 95,
            "spo2": 96.5,
            "temperature": 98.6,
            "blood_pressure_sys": 142,
            "blood_pressure_dia": 88,
            "respiration_rate": 18,
            "ecg_status": "Sinus Tachycardia"
        },
        {
            "patient_id": patient_id,
            "entry_id": entry_id,
            "heart_rate": 88,
            "spo2": 97.2,
            "temperature": 98.5,
            "blood_pressure_sys": 135,
            "blood_pressure_dia": 82,
            "respiration_rate": 16,
            "ecg_status": "Normal Sinus Rhythm"
        },
        {
            "patient_id": patient_id,
            "entry_id": entry_id,
            "heart_rate": 82,
            "spo2": 98.1,
            "temperature": 98.4,
            "blood_pressure_sys": 128,
            "blood_pressure_dia": 78,
            "respiration_rate": 14,
            "ecg_status": "Normal Sinus Rhythm"
        }
    ]
    
    for vital in vital_readings:
        reading_id = patient_db.add_vital_reading(vital)
        print(f"✓ Vital reading recorded: {reading_id}")
        print(f"  HR: {vital['heart_rate']}, SpO2: {vital['spo2']}%, BP: {vital['blood_pressure_sys']}/{vital['blood_pressure_dia']}")
    
    # Retrieve vitals
    vitals = patient_db.get_entry_vital_readings(entry_id)
    print(f"\n✓ Retrieved {len(vitals)} vital reading(s)")
    
    return entry_id


def test_analysis_results(patient_id, entry_id):
    """Test saving analysis results"""
    print_section("TEST 4: Saving Analysis Results")
    
    analysis_data = {
        "patient_id": patient_id,
        "entry_id": entry_id,
        "ml_risk_level": "Medium",
        "rule_engine_risk": "Medium",
        "overall_risk": "Medium",
        "confidence": 87,
        "bleeding_risk": "Low",
        "movement_risk": "Medium",
        "posture_risk": "Low",
        "diagnosis": "Acute Coronary Syndrome (ACS) - Unstable Angina",
        "recommended_condition": "Undifferentiated Chest Pain/Tachycardia",
        "medications": [
            {"name": "Aspirin", "dosage": "300 mg", "frequency": "Once", "purpose": "Antiplatelet support"},
            {"name": "Nitroglycerin", "dosage": "0.4 mg SL", "frequency": "Every 5 min x3", "purpose": "Symptomatic relief"},
            {"name": "Metoprolol", "dosage": "25 mg", "frequency": "As directed", "purpose": "Rate control"}
        ]
    }
    
    analysis_id = patient_db.add_analysis_result(analysis_data)
    print(f"✓ Analysis result saved successfully")
    print(f"  Analysis ID: {analysis_id}")
    print(f"  ML Risk: {analysis_data['ml_risk_level']}")
    print(f"  Overall Risk: {analysis_data['overall_risk']}")
    print(f"  Confidence: {analysis_data['confidence']}%")
    print(f"  Diagnosis: {analysis_data['diagnosis']}")
    print(f"  Medications: {len(analysis_data['medications'])} prescribed")
    
    # Retrieve analysis
    analysis = patient_db.get_latest_analysis(entry_id)
    if analysis:
        print(f"\n✓ Analysis retrieved successfully")
        print(f"  Risk Level: {analysis['overall_risk']}")
        if analysis.get('medications'):
            print(f"  Medications from DB: {analysis['medications'][0]['name']} - {analysis['medications'][0]['dosage']}")


def test_events(patient_id, entry_id):
    """Test recording events"""
    print_section("TEST 5: Recording Events")
    
    events = [
        {
            "event_type": "Admission",
            "event_description": "Patient admitted via Emergency"
        },
        {
            "event_type": "Vitals Updated",
            "event_description": "Vital signs recorded at T+5 mins"
        },
        {
            "event_type": "Analysis Complete",
            "event_description": "AI analysis completed - Medium risk determined"
        },
        {
            "event_type": "Medication Administered",
            "event_description": "Aspirin 300mg administered by paramedic"
        }
    ]
    
    for event in events:
        event_id = patient_db.add_event({
            "patient_id": patient_id,
            "entry_id": entry_id,
            **event,
            "event_status": "Completed"
        })
        print(f"✓ Event recorded: {event_id}")
        print(f"  Type: {event['event_type']}")
        print(f"  Description: {event['event_description']}")
    
    # Retrieve events
    retrieved_events = patient_db.get_entry_events(entry_id)
    print(f"\n✓ Retrieved {len(retrieved_events)} event(s)")


def test_statistics():
    """Test statistics and reporting"""
    print_section("TEST 6: Statistics & Reporting")
    
    patients_today = patient_db.get_patients_today()
    print(f"✓ Patients admitted today: {patients_today}")
    
    recent_summary = patient_db.get_recent_patient_summary(limit=5)
    print(f"✓ Retrieved recent patient summary: {len(recent_summary)} patient(s)")
    
    for patient in recent_summary:
        print(f"\n  Patient: {patient['name']}")
        print(f"    Chief Complaint: {patient['chief_complaint']}")
        print(f"    Latest HR: {patient['latest_hr']}")
        print(f"    Latest SpO2: {patient['latest_spo2']}")
        print(f"    Risk Level: {patient['latest_risk']}")


def test_helper_functions(patient_id):
    """Test high-level helper functions"""
    print_section("TEST 7: Testing Helper Functions")
    
    # Get complete patient record
    record = get_patient_complete_record(patient_id)
    
    if record:
        print(f"✓ Complete patient record retrieved")
        print(f"  Patient: {record['patient']['name']}")
        print(f"  Entries: {len(record['entries'])}")
        print(f"  Vitals: {len(record['vitals'])}")
        print(f"  Analysis: {'Yes' if record['analysis'] else 'No'}")
        print(f"  Events: {len(record['events'])}")
        
        # Print sample analysis
        if record['analysis']:
            print(f"\n  Latest Analysis:")
            print(f"    Diagnosis: {record['analysis'].get('diagnosis')}")
            print(f"    Risk: {record['analysis'].get('overall_risk')}")
            print(f"    Confidence: {record['analysis'].get('confidence')}%")


def test_save_admission_flow():
    """Test complete admission flow with helper functions"""
    print_section("TEST 8: Complete Admission Flow")
    
    # Create patient info
    patient_info = {
        "id": "TEST-PAT-FLOW",
        "name": "Sarah Johnson",
        "age": 38,
        "dob": "1988-03-15",
        "past_conditions": "Asthma",
        "allergies": "None",
        "chief_complaint": "Severe respiratory distress",
        "initial_condition": "Acute Respiratory Failure"
    }
    
    # Save admission
    entry_id = save_patient_admission(patient_info, ambulance_unit="Unit-02", paramedic_name="Jane Paramedic")
    print(f"✓ Admission saved: {entry_id}")
    
    # Save vitals
    sensors = {
        "heart_rate": "110 BPM",
        "spo2": "88%",
        "temp": "99.2°F",
        "blood_pressure": "145/90 mmHg",
        "resp_rate": "28 RR",
        "ecg_status": "Sinus Tachycardia"
    }
    reading_id = save_vital_signs(patient_info["id"], entry_id, sensors)
    print(f"✓ Vitals saved: {reading_id}")
    
    # Save analysis
    ai_results = {
        "ml_risk": "High",
        "risk_level": "High",
        "confidence": 92,
        "diagnosis": "Acute Respiratory Distress Syndrome (ARDS)",
        "medications": [
            {"name": "Salbutamol Neb", "dosage": "2.5 mg"}
        ]
    }
    analysis_id = save_analysis_result(patient_info["id"], entry_id, ai_results)
    print(f"✓ Analysis saved: {analysis_id}")
    
    # Save event
    event_id = save_event(patient_info["id"], entry_id, "Emergency Admission", "High-risk respiratory patient")
    print(f"✓ Event saved: {event_id}")


def test_historical_records(patient_id, entry_id):
    """Test historical records functionality"""
    print_section("TEST 9: Historical Records Management")
    
    # Add custom historical record
    record_id = add_to_historical_records(
        patient_id,
        entry_id,
        {
            "accuracy": 92,
            "response_time": 4,
            "status": "Recovered",
            "diagnosis": "Acute Coronary Syndrome",
            "notes": "Successful intervention with aspirin and nitroglycerin"
        }
    )
    print(f"✓ Historical record added: {record_id}")
    
    # Get historical records
    records = patient_db.get_historical_records(limit=5)
    print(f"✓ Retrieved {len(records)} historical record(s)")
    if records:
        print(f"  Latest: {records[0]['name']} - {records[0]['condition']}")


def test_historical_analytics():
    """Test historical analytics"""
    print_section("TEST 10: Historical Analytics")
    
    analytics = get_historical_analytics(days=30)
    
    print(f"✓ Analytics retrieved")
    print(f"  Total records (30 days): {analytics['total_records']}")
    print(f"  Average accuracy: {analytics['avg_accuracy']}%")
    print(f"  Average response time: {analytics['avg_response_time']} minutes")
    
    if analytics['status_breakdown']:
        print(f"  Status breakdown:")
        for status, count in analytics['status_breakdown'].items():
            print(f"    - {status}: {count}")
    
    if analytics['top_conditions']:
        print(f"  Top conditions:")
        for cond in analytics['top_conditions']:
            print(f"    - {cond['condition']}: {cond['count']} cases")


def test_sync_entry_to_history():
    """Test syncing entry to historical records"""
    print_section("TEST 11: Sync Entry to Historical Records")
    
    # Create an admission first
    patient_info = {
        "id": "TEST-PAT-SYNC",
        "name": "Robert Williams",
        "age": 67,
        "chief_complaint": "Acute Stroke"
    }
    
    entry_id = save_patient_admission(patient_info, ambulance_unit="Unit-03")
    print(f"✓ Test admission created: {entry_id}")
    
    # Sync to historical records
    record_id = sync_entry_to_history(
        entry_id,
        status="Recovered",
        accuracy=94,
        response_time=3
    )
    print(f"✓ Entry synced to historical records: {record_id}")
    
    # Verify the record exists
    hist_records = patient_db.get_historical_records(limit=1)
    if hist_records:
        print(f"✓ Verification successful - Latest entry in history:")
        print(f"  Name: {hist_records[0]['name']}")
        print(f"  Status: {hist_records[0]['status']}")
        print(f"  Accuracy: {hist_records[0]['accuracy']}%")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print(" AMBULANCE SYSTEM - DATABASE TEST SUITE")
    print("="*60)
    print(f" Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Run tests
        patient_id = test_add_patient()
        entry_id = test_patient_admission(patient_id)
        test_vital_signs(patient_id, entry_id)
        test_analysis_results(patient_id, entry_id)
        test_events(patient_id, entry_id)
        test_statistics()
        test_helper_functions(patient_id)
        test_save_admission_flow()
        test_historical_records(patient_id, entry_id)
        test_historical_analytics()
        test_sync_entry_to_history()
        
        # Summary
        print_section("RESULTS SUMMARY")
        print("✓ All tests completed successfully!")
        print("\nDatabase File Location:")
        print(f"  {patient_db.db_path}")
        
        # Show tables
        conn = patient_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        
        print(f"\nDatabase Tables Created:")
        for table in tables:
            print(f"  ✓ {table[0]}")
        
        print(f"\nEnd Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n" + "="*60 + "\n")
        
        return True
        
    except Exception as e:
        print_section("ERROR")
        print(f"✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
