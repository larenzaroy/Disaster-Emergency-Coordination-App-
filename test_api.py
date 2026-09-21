"""
Automated Test Suite for ResQNet Emergency & Disaster Management System.
Runs test requests against FastAPI backend endpoints directly using TestClient.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    print("Testing /api/health ...")
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    print("  [PASS] Health check OK")

def test_hospitals_and_blood():
    print("Testing /api/hospitals with blood & oxygen filters ...")
    # All hospitals
    res = client.get("/api/hospitals")
    assert res.status_code == 200
    hospitals = res.json()
    assert len(hospitals) >= 5
    print(f"  [PASS] Found {len(hospitals)} hospitals")

    # Filter by O- blood group
    res_o_neg = client.get("/api/hospitals?blood_group=O-")
    assert res_o_neg.status_code == 200
    o_neg_hospitals = res_o_neg.json()
    for h in o_neg_hospitals:
        assert h["blood_inventory"].get("O-", 0) > 0
    print(f"  [PASS] Filtered {len(o_neg_hospitals)} hospitals with O- blood in stock")

    # Filter by high oxygen
    res_o2 = client.get("/api/hospitals?min_oxygen=70")
    assert res_o2.status_code == 200
    o2_hospitals = res_o2.json()
    for h in o2_hospitals:
        assert h["liquid_oxygen_percentage"] >= 70 or h["oxygen_cylinders_available"] >= 10
    print(f"  [PASS] Filtered {len(o2_hospitals)} hospitals with high oxygen levels")

def test_sos_dispatch():
    print("Testing One-Tap SOS Dispatch /api/sos ...")
    payload = {
        "caller_name": "Dr. Test Runner",
        "phone": "+91-99999-11111",
        "disaster_type": "CARDIAC",
        "severity": "CRITICAL",
        "latitude": 22.5726,
        "longitude": 88.3639,
        "address": "College Street Metro, Kolkata",
        "patient_id": "P-101",
        "notes": "Severe crushing chest pain, diaphoresis."
    }
    res = client.post("/api/sos", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "emergency_id" in data
    assert data["status"] == "DISPATCHED"
    assert data["assigned_ambulance"] is not None
    assert data["assigned_hospital"]["id"] is not None
    print(f"  [PASS] SOS Triggered: {data['emergency_id']} -> Assigned Amb: {data['assigned_ambulance']}, Hosp: {data['assigned_hospital']['name']}")
    return data["emergency_id"]

def test_routing_and_green_corridor():
    print("Testing Ambulance Route & Green Corridor /api/route ...")
    res = client.get("/api/route?ambulance_id=AMB-101&target_lat=22.5726&target_lon=88.3639&destination_hospital_id=HOSP-01")
    assert res.status_code == 200
    data = res.json()
    assert "full_waypoints" in data
    assert len(data["full_waypoints"]) > 10
    analytics = data["corridor_analytics"]
    assert analytics["total_distance_km"] > 0
    assert analytics["minutes_saved"] > 0
    print(f"  [PASS] Route Waypoints: {len(data['full_waypoints'])}, Normal ETA: {analytics['normal_eta_mins']}m, Priority ETA: {analytics['priority_eta_mins']}m (Saved {analytics['minutes_saved']}m)")

    # Toggle green corridor
    print("Testing Green Corridor Preemption Toggle ...")
    toggle_res = client.post("/api/green-corridor/toggle?ambulance_id=AMB-101&activate=true")
    assert toggle_res.status_code == 200
    print("  [PASS] Green corridor toggled successfully")

def test_patient_ehr():
    print("Testing Doctor Emergency EHR Access /api/patient/P-101 ...")
    res = client.get("/api/patient/P-101?emergency_override=true")
    assert res.status_code == 200
    patient = res.json()
    assert patient["full_name"] == "Aarav Sharma"
    assert patient["blood_group"] == "O-"
    assert "Severe Penicillin Allergy" in patient["known_allergies"]
    print(f"  [PASS] Retrieved EHR for {patient['full_name']} (Blood: {patient['blood_group']}, Allergies: {patient['known_allergies']})")

def test_prescription_simplifier():
    print("Testing AI Prescription & Jargon Simplifier /api/simplify ...")
    sample_text = (
        "Pt presented with acute dyspnea, tachycardia, and bilateral wheezing. "
        "Rx: Tab Augmentin 625mg PO TID PC x 7d. Neb Salbutamol STAT and PRN. Tab Dolo 650mg SOS."
    )
    res = client.post("/api/simplify", json={"text": sample_text})
    assert res.status_code == 200
    data = res.json()
    assert len(data["medications"]) >= 2
    assert len(data["jargon_detected"]) >= 2
    assert len(data["safety_alerts"]) >= 1
    assert "speech_text" in data
    print(f"  [PASS] Simplifier parsed {len(data['medications'])} drugs, {len(data['jargon_detected'])} jargon terms, and flagged allergy alert: {data['safety_alerts'][0]}")

def test_triage_calculator():
    print("Testing START Disaster Triage Calculator /api/triage/calculate ...")
    # Immediate / Critical case (cannot walk, breathing fast > 30)
    res_red = client.post("/api/triage/calculate", json={
        "can_walk": False,
        "respiration_rate": 34,
        "radial_pulse_present": True,
        "follows_commands": True
    })
    assert res_red.status_code == 200
    assert res_red.json()["tag"] == "RED"
    print("  [PASS] Triage calculated RED tag for rapid breathing casualty")

    # Minor / Walking case
    res_green = client.post("/api/triage/calculate", json={
        "can_walk": True,
        "respiration_rate": 20,
        "radial_pulse_present": True,
        "follows_commands": True
    })
    assert res_green.status_code == 200
    assert res_green.json()["tag"] == "GREEN"
    print("  [PASS] Triage calculated GREEN tag for walking casualty")

def test_stats_and_broadcasts():
    print("Testing System KPI Stats & Broadcasts ...")
    stats_res = client.get("/api/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "available_beds" in stats
    assert "total_blood_units" in stats
    print(f"  [PASS] System Stats: Available Beds: {stats['available_beds']}, Total Blood Units: {stats['total_blood_units']}")

    broadcast_res = client.get("/api/broadcasts")
    assert broadcast_res.status_code == 200
    broadcasts = broadcast_res.json()
    assert len(broadcasts) >= 1
    print(f"  [PASS] Active Disaster Broadcast: {broadcasts[0]['title']}")

def test_multiple_ambulances():
    print("Testing Multiple Ambulances Simultaneous Dispatch & Lifecycle ...")
    # 1. Dispatch emergency with 2 ambulances simultaneously
    payload = {
        "caller_name": "Major Rescue Team",
        "phone": "+91-88888-22222",
        "disaster_type": "ACCIDENT",
        "severity": "CRITICAL",
        "latitude": 22.5650,
        "longitude": 88.3550,
        "address": "Park Street Crossing, Kolkata",
        "ambulance_count": 2,
        "notes": "Multi-vehicle pileup with several casualties."
    }
    res = client.post("/api/sos", json=payload)
    assert res.status_code == 200
    data = res.json()
    emg_id = data["emergency_id"]
    assigned_ambs = data.get("assigned_ambulances", [])
    assert len(assigned_ambs) == 2, f"Expected 2 ambulances dispatched, got {len(assigned_ambs)}"
    print(f"  [PASS] Dispatched 2 ambulances simultaneously: {[a['ambulance_id'] for a in assigned_ambs]}")
    assert assigned_ambs[0]["status"] in ["ACCEPTED", "REQUESTED"]
    assert assigned_ambs[1]["status"] in ["ACCEPTED", "REQUESTED"]

    # 2. Request an additional ambulance for the same emergency
    more_res = client.post(f"/api/emergencies/{emg_id}/request-ambulance", json={"notes": "Need pediatric ALS unit"})
    assert more_res.status_code == 200
    more_data = more_res.json()
    assert len(more_data["assigned_ambulances"]) == 3, "Expected 3 ambulances after requesting additional"
    new_amb = more_data["newly_assigned"]
    new_amb_id = new_amb.get("ambulance_id") or new_amb.get("id")
    print(f"  [PASS] Requested additional ambulance: {new_amb_id} (Total: 3)")

    # 3. Transition status of individual ambulances
    amb1_id = assigned_ambs[0]["ambulance_id"]
    amb2_id = assigned_ambs[1]["ambulance_id"]

    # Amb 1: ACCEPTED -> ON_THE_WAY
    st1 = client.put(f"/api/emergencies/{emg_id}/ambulances/{amb1_id}/status", json={"status": "ACCEPTED"})
    assert st1.status_code == 200
    assert st1.json()["current_status"] == "ACCEPTED"

    st1_onway = client.put(f"/api/emergencies/{emg_id}/ambulances/{amb1_id}/status", json={"status": "ON_THE_WAY"})
    assert st1_onway.status_code == 200
    assert st1_onway.json()["current_status"] == "ON_THE_WAY"

    # Amb 2: ARRIVED
    st2 = client.put(f"/api/emergencies/{emg_id}/ambulances/{amb2_id}/status", json={"status": "ARRIVED"})
    assert st2.status_code == 200
    assert st2.json()["current_status"] == "ARRIVED"

    # Verify in emergency list that all assigned ambulances maintain separate statuses
    list_res = client.get("/api/emergencies")
    assert list_res.status_code == 200
    all_emgs = list_res.json()
    target_emg = next(e for e in all_emgs if e["id"] == emg_id)
    amb_status_map = {a["ambulance_id"]: a["status"] for a in target_emg["assigned_ambulances"]}
    assert amb_status_map[amb1_id] == "ON_THE_WAY"
    assert amb_status_map[amb2_id] == "ARRIVED"
    print(f"  [PASS] Independent status lifecycle verified across all assigned ambulances: {amb_status_map}")


def test_editable_medical_history():
    print("Testing Editable Medical History /api/patient/{id} ...")
    # Update Aarav's profile
    update_payload = {
        "chronic_conditions": ["Hypertension (Stage 1)", "Mild Asthma"],
        "emergency_contacts": [{"name": "Sunita Sharma (Spouse)", "phone": "+91-98765-43211"}],
        "known_allergies": ["Severe Penicillin Allergy", "Peanuts"],
        "past_surgeries": "Appendectomy (2018), Arthroscopy (2023)"
    }
    update_res = client.put("/api/patient/P-101", json=update_payload)
    assert update_res.status_code == 200
    updated_patient = update_res.json()["patient"]
    assert "Hypertension (Stage 1)" in updated_patient["chronic_conditions"]
    assert "Peanuts" in updated_patient["known_allergies"]
    assert updated_patient["emergency_contacts"][0]["name"] == "Sunita Sharma (Spouse)"
    print("  [PASS] Patient medical history updated successfully and verified via PUT response")

    # Fetch with GET to confirm persistent storage in SQLite
    get_res = client.get("/api/patient/P-101")
    assert get_res.status_code == 200
    fetched_patient = get_res.json()
    assert "Hypertension (Stage 1)" in fetched_patient["chronic_conditions"]
    assert fetched_patient["emergency_contacts"][0]["name"] == "Sunita Sharma (Spouse)"
    print("  [PASS] Persistent storage in SQLite verified via GET /api/patient/P-101")


def test_current_medication_management():
    print("Testing Current Medication Management (Add, Retain without overwrite, Edit, Delete) ...")
    # Get initial count
    init_res = client.get("/api/patient/P-101/medications")
    assert init_res.status_code == 200
    init_data = init_res.json()
    init_meds = init_data if isinstance(init_data, list) else init_data.get("medications", [])
    initial_count = len(init_meds)
    print(f"  Initial medications count: {initial_count}")

    # 1. Add Medicine A
    med_a = {
        "name": "Atorvastatin",
        "dosage": "20mg",
        "frequency": "Once daily at bedtime",
        "start_date": "2026-01-10",
        "end_date": "2026-12-31",
        "notes": "Lipid profile management"
    }
    res_a = client.post("/api/patient/P-101/medications", json=med_a)
    assert res_a.status_code == 200
    med_a_id = res_a.json()["medication_id"]
    print(f"  [PASS] Added Medicine A ({med_a['name']}, ID: {med_a_id})")

    # 2. Add Medicine B (Must NOT overwrite Medicine A)
    med_b = {
        "name": "Metformin",
        "dosage": "500mg",
        "frequency": "Twice daily after meals",
        "start_date": "2026-02-01",
        "end_date": "",
        "notes": "Glycemic control"
    }
    res_b = client.post("/api/patient/P-101/medications", json=med_b)
    assert res_b.status_code == 200
    med_b_id = res_b.json()["medication_id"]
    print(f"  [PASS] Added Medicine B ({med_b['name']}, ID: {med_b_id})")

    # 3. Add Medicine C (Must NOT overwrite Medicine A or B)
    med_c = {
        "name": "Vitamin D3",
        "dosage": "60,000 IU",
        "frequency": "Weekly once",
        "start_date": "2026-03-01",
        "end_date": "2026-05-01",
        "notes": "Post breakfast on Sundays"
    }
    res_c = client.post("/api/patient/P-101/medications", json=med_c)
    assert res_c.status_code == 200
    med_c_id = res_c.json()["medication_id"]
    print(f"  [PASS] Added Medicine C ({med_c['name']}, ID: {med_c_id})")

    # Verify all 3 medicines + initial medications exist simultaneously!
    chk_res = client.get("/api/patient/P-101/medications")
    chk_data = chk_res.json()
    current_meds = chk_data if isinstance(chk_data, list) else chk_data.get("medications", [])
    current_med_ids = [m["id"] for m in current_meds]
    assert med_a_id in current_med_ids, "Medicine A missing!"
    assert med_b_id in current_med_ids, "Medicine B missing!"
    assert med_c_id in current_med_ids, "Medicine C missing!"
    assert len(current_meds) == initial_count + 3, f"Expected {initial_count + 3} medications, got {len(current_meds)}"
    print(f"  [PASS] Verified non-overwriting behavior: All {len(current_meds)} medications retained successfully!")

    # 4. Edit Medicine B dosage
    edit_payload = {
        "name": "Metformin Extended Release",
        "dosage": "1000mg",
        "frequency": "Once daily with dinner",
        "start_date": "2026-02-01",
        "end_date": "",
        "notes": "Switched to ER formulation"
    }
    edit_res = client.put(f"/api/patient/P-101/medications/{med_b_id}", json=edit_payload)
    assert edit_res.status_code == 200
    assert edit_res.json()["medication"]["dosage"] == "1000mg"
    print("  [PASS] Edited Medicine B successfully to 1000mg")

    # 5. Delete Medicine C
    del_res = client.delete(f"/api/patient/P-101/medications/{med_c_id}")
    assert del_res.status_code == 200
    final_res = client.get("/api/patient/P-101/medications")
    final_data = final_res.json()
    final_meds = final_data if isinstance(final_data, list) else final_data.get("medications", [])
    final_ids = [m["id"] for m in final_meds]
    assert med_c_id not in final_ids, "Medicine C was not deleted!"
    assert med_a_id in final_ids, "Medicine A was incorrectly removed!"
    assert med_b_id in final_ids, "Medicine B was incorrectly removed!"
    print("  [PASS] Deleted Medicine C; Medicine A and updated Medicine B securely preserved.")

def test_unified_3_portal_auth_and_routing():
    print("Testing Unified 3-Portal Authentication & Role-Based Routing (/api/auth/login, /patient, /doctor, /ambulance) ...")
    # 1. Patient Login
    res_p = client.post('/api/auth/login', json={'email': 'patient@demo.com'})
    assert res_p.status_code == 200
    data_p = res_p.json()
    assert data_p['success'] is True
    assert data_p['role'] == 'PATIENT'
    assert data_p['portal'] == 'patient'
    assert data_p['redirect_url'] == '/patient'
    assert 'token' in data_p
    print("  [PASS] Patient Portal Authentication (/api/auth/login -> /patient)")

    # 2. Doctor Login
    res_d = client.post('/api/auth/login', json={'email': 'doctor@demo.com'})
    assert res_d.status_code == 200
    data_d = res_d.json()
    assert data_d['success'] is True
    assert data_d['role'] == 'DOCTOR'
    assert data_d['portal'] == 'doctor'
    assert data_d['redirect_url'] == '/doctor'
    print("  [PASS] Doctor Portal Authentication (/api/auth/login -> /doctor)")

    # 3. Ambulance Login
    res_a = client.post('/api/auth/login', json={'email': 'ambulance@demo.com'})
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a['success'] is True
    assert data_a['role'] == 'AMBULANCE'
    assert data_a['portal'] == 'ambulance'
    assert data_a['redirect_url'] == '/ambulance'
    print("  [PASS] Ambulance Portal Authentication (/api/auth/login -> /ambulance)")

    # 4. Role-based Route Serving
    for route in ['/patient', '/doctor', '/ambulance', '/portal/patient', '/portal/doctor', '/portal/ambulance']:
        res_r = client.get(route)
        assert res_r.status_code == 200
        assert '<!DOCTYPE html>' in res_r.text
    print("  [PASS] Verified 6 Role-based portal routes serving Unified 3-Portal UI")


if __name__ == "__main__":
    print("==================================================")
    print("RUNNING RAKSHA RESQNET COMPREHENSIVE ENDPOINT VERIFICATION")
    print("==================================================")
    test_health()
    test_hospitals_and_blood()
    emg_id = test_sos_dispatch()
    test_multiple_ambulances()
    test_routing_and_green_corridor()
    test_patient_ehr()
    test_editable_medical_history()
    test_current_medication_management()
    test_prescription_simplifier()
    test_triage_calculator()
    test_stats_and_broadcasts()
    test_unified_3_portal_auth_and_routing()
    print("==================================================")
    print("ALL 12 TEST SUITES PASSED FLAWLESSLY! 100% SUCCESS.")
    print("==================================================")


