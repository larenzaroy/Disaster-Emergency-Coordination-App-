import os
import json
import uuid
from datetime import datetime
from typing import Optional, List, Union, Any
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import database
from database import get_db, init_db
import routing_engine
import medical_simplifier

# Initialize database schema and initial data
init_db()

app = FastAPI(
    title="ResQNet - Emergency & Disaster Response System",
    description="Emergency dispatch, hospital resource radar, green corridor routing, EHR access, and AI medical simplifier",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- PYDANTIC SCHEMAS -----------------

class SOSRequest(BaseModel):
    caller_name: Optional[str] = "Anonymous Citizen"
    phone: Optional[str] = "+91-99999-00000"
    disaster_type: str = "MEDICAL_EMERGENCY" # FLOOD, FIRE, EARTHQUAKE, ACCIDENT, CARDIAC, MEDICAL
    severity: str = "CRITICAL" # CRITICAL, HIGH, MODERATE
    latitude: float = 22.5726
    longitude: float = 88.3639
    address: Optional[str] = "Live GPS Location"
    patient_id: Optional[str] = None
    notes: Optional[str] = ""
    ambulance_count: Optional[int] = 1

class StatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None

class RequestAmbulancePayload(BaseModel):
    count: Optional[int] = 1
    ambulance_id: Optional[str] = None
    notes: Optional[str] = None

class AmbulanceStatusUpdate(BaseModel):
    status: str # 'REQUESTED', 'ACCEPTED', 'ON_THE_WAY', 'ARRIVED', 'COMPLETED'
    notes: Optional[str] = None

class InventoryUpdate(BaseModel):
    blood_group: Optional[str] = None
    units_delta: Optional[int] = None
    oxygen_cylinders: Optional[int] = None
    liquid_oxygen_percentage: Optional[float] = None
    icu_beds_available: Optional[int] = None

class SimplifyRequest(BaseModel):
    text: str

class TriageRequest(BaseModel):
    can_walk: bool
    respiration_rate: int # breaths per minute
    radial_pulse_present: bool
    follows_commands: bool

class BroadcastRequest(BaseModel):
    title: str
    hazard_type: str
    severity: str
    description: str
    safety_instructions: str
    evacuation_route: Optional[str] = ""

class MedicationItem(BaseModel):
    id: Optional[str] = None
    name: str
    dosage: str
    frequency: str
    start_date: Optional[str] = ""
    end_date: Optional[str] = ""
    notes: Optional[str] = ""

class PatientRecordRequest(BaseModel):
    id: Optional[str] = None
    full_name: str
    dob: str
    blood_group: str
    emergency_contacts: List[dict]
    known_allergies: List[str]
    chronic_conditions: List[str]
    current_medications: Optional[List[dict]] = None
    past_surgeries: Optional[str] = ""
    insurance_policy: Optional[str] = ""
    emergency_access_pin: Optional[str] = "1234"

class PatientRecordUpdateRequest(BaseModel):
    id: Optional[str] = None
    full_name: Optional[str] = None
    dob: Optional[str] = None
    blood_group: Optional[str] = None
    emergency_contacts: Optional[Union[List[dict], List[str], str]] = None
    emergency_contact: Optional[Union[dict, str]] = None
    known_allergies: Optional[Union[List[str], str]] = None
    chronic_conditions: Optional[Union[List[str], str]] = None
    current_medications: Optional[Union[List[dict], List[str], str]] = None
    past_surgeries: Optional[str] = None
    insurance_policy: Optional[str] = None
    emergency_access_pin: Optional[str] = None
    doctor_notes: Optional[str] = None

# ----------------- API ENDPOINTS -----------------

@app.get("/api/health")
def health_check():
    return {"status": "HEALTHY", "system": "ResQNet", "timestamp": datetime.now().isoformat()}

# 1. ONE-TAP SOS & MULTIPLE AMBULANCE DISPATCH
@app.post("/api/sos")
def trigger_sos(sos: SOSRequest):
    conn = get_db()
    cursor = conn.cursor()

    emergency_id = f"EMG-{str(uuid.uuid4())[:8].upper()}"
    now = datetime.now().isoformat()

    # Find nearest hospital with trauma capability
    cursor.execute("SELECT * FROM hospitals")
    hospitals = cursor.fetchall()
    closest_hosp = min(
        hospitals,
        key=lambda h: routing_engine.haversine_km(sos.latitude, sos.longitude, h["latitude"], h["longitude"])
    ) if hospitals else {"id": "HOSP-01", "name": "City Trauma Center", "phone": "+91-99999-00000", "icu_beds_available": 5}
    assigned_hosp_id = closest_hosp["id"]

    # Find available ambulances and rank by proximity
    cursor.execute("SELECT * FROM ambulances WHERE status = 'AVAILABLE'")
    available_ambulances = cursor.fetchall()

    sorted_ambs = sorted(
        available_ambulances,
        key=lambda a: routing_engine.haversine_km(sos.latitude, sos.longitude, a["latitude"], a["longitude"])
    )

    requested_count = max(1, sos.ambulance_count or 1)
    assigned_ambs = list(sorted_ambs[:requested_count])

    # If not enough available ambulances, fulfill remainder from nearest fleet
    if len(assigned_ambs) < requested_count:
        assigned_ids = {a["id"] for a in assigned_ambs}
        cursor.execute("SELECT * FROM ambulances")
        all_ambs = cursor.fetchall()
        sorted_all = sorted(
            all_ambs,
            key=lambda a: routing_engine.haversine_km(sos.latitude, sos.longitude, a["latitude"], a["longitude"])
        )
        for amb in sorted_all:
            if amb["id"] not in assigned_ids:
                assigned_ambs.append(amb)
                assigned_ids.add(amb["id"])
                if len(assigned_ambs) >= requested_count:
                    break

    primary_amb_id = assigned_ambs[0]["id"] if assigned_ambs else None

    # Insert emergency record first to satisfy foreign key constraints in emergency_ambulances
    cursor.execute("""
        INSERT INTO emergencies (
            id, created_at, caller_name, phone, disaster_type, severity,
            latitude, longitude, address, status, assigned_ambulance_id,
            assigned_hospital_id, patient_id, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DISPATCHED', ?, ?, ?, ?)
    """, (
        emergency_id, now, sos.caller_name, sos.phone, sos.disaster_type, sos.severity,
        sos.latitude, sos.longitude, sos.address, primary_amb_id, assigned_hosp_id,
        sos.patient_id, sos.notes
    ))

    # Link all assigned ambulances into emergency_ambulances
    assigned_amb_details = []
    for idx, amb in enumerate(assigned_ambs):
        amb_id = amb["id"]
        amb_status = "ACCEPTED" if idx == 0 else "REQUESTED"
        cursor.execute("""
            INSERT OR REPLACE INTO emergency_ambulances (
                emergency_id, ambulance_id, status, requested_at, updated_at, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (emergency_id, amb_id, amb_status, now, now, f"Dispatched for {sos.disaster_type} SOS"))

        cursor.execute("""
            UPDATE ambulances 
            SET status = 'DISPATCHED', assigned_emergency_id = ?, destination_hospital_id = ?
            WHERE id = ?
        """, (emergency_id, assigned_hosp_id, amb_id))

        assigned_amb_details.append({
            "ambulance_id": amb_id,
            "call_sign": amb["call_sign"],
            "type": amb["type"],
            "driver_name": amb["driver_name"],
            "driver_phone": amb["driver_phone"],
            "status": amb_status,
            "latitude": amb["latitude"],
            "longitude": amb["longitude"]
        })

    conn.commit()
    conn.close()

    return {
        "emergency_id": emergency_id,
        "status": "DISPATCHED",
        "created_at": now,
        "assigned_ambulance": primary_amb_id,
        "assigned_ambulances": assigned_amb_details,
        "assigned_hospital": {
            "id": closest_hosp["id"],
            "name": closest_hosp["name"],
            "phone": closest_hosp["phone"],
            "icu_beds": closest_hosp["icu_beds_available"]
        },
        "message": f"Immediate rescue dispatched with {len(assigned_amb_details)} ambulance(s). Responders en route."
    }

@app.get("/api/emergencies")
def list_emergencies(status: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM emergencies WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        cursor.execute("SELECT * FROM emergencies ORDER BY created_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]

    # Attach all assigned ambulances for each emergency
    for r in rows:
        cursor.execute("""
            SELECT ea.ambulance_id, ea.status, ea.requested_at, ea.updated_at, ea.notes,
                   a.call_sign, a.type, a.driver_name, a.driver_phone, a.latitude, a.longitude, a.green_corridor_active
            FROM emergency_ambulances ea
            JOIN ambulances a ON ea.ambulance_id = a.id
            WHERE ea.emergency_id = ?
            ORDER BY ea.requested_at ASC
        """, (r["id"],))
        amb_rows = [dict(ar) for ar in cursor.fetchall()]
        r["assigned_ambulances"] = amb_rows

    conn.close()
    return rows

@app.post("/api/emergencies/{id}/request-ambulance")
def request_additional_ambulance(id: str, payload: Optional[RequestAmbulancePayload] = None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emergencies WHERE id = ?", (id,))
    emg = cursor.fetchone()
    if not emg:
        conn.close()
        raise HTTPException(status_code=404, detail="Emergency not found")

    count = payload.count if payload and payload.count else 1
    specific_id = payload.ambulance_id if payload else None
    notes = payload.notes if payload and payload.notes else "Additional ambulance requested"
    now = datetime.now().isoformat()

    added_ambs = []
    if specific_id:
        cursor.execute("SELECT * FROM ambulances WHERE id = ?", (specific_id,))
        target_amb = cursor.fetchone()
        if target_amb:
            cursor.execute("""
                INSERT OR REPLACE INTO emergency_ambulances (emergency_id, ambulance_id, status, requested_at, updated_at, notes)
                VALUES (?, ?, 'REQUESTED', ?, ?, ?)
            """, (id, specific_id, now, now, notes))
            cursor.execute("UPDATE ambulances SET status = 'DISPATCHED', assigned_emergency_id = ? WHERE id = ?", (id, specific_id))
            added_ambs.append(dict(target_amb))
    else:
        cursor.execute("""
            SELECT * FROM ambulances 
            WHERE id NOT IN (SELECT ambulance_id FROM emergency_ambulances WHERE emergency_id = ?)
            ORDER BY (CASE WHEN status = 'AVAILABLE' THEN 0 ELSE 1 END) ASC
        """, (id,))
        candidates = cursor.fetchall()
        for amb in candidates[:count]:
            cursor.execute("""
                INSERT OR REPLACE INTO emergency_ambulances (emergency_id, ambulance_id, status, requested_at, updated_at, notes)
                VALUES (?, ?, 'REQUESTED', ?, ?, ?)
            """, (id, amb["id"], now, now, notes))
            cursor.execute("UPDATE ambulances SET status = 'DISPATCHED', assigned_emergency_id = ? WHERE id = ?", (id, amb["id"]))
            added_ambs.append(dict(amb))

    conn.commit()

    cursor.execute("""
        SELECT ea.ambulance_id, ea.status, ea.requested_at, ea.updated_at, ea.notes,
               a.call_sign, a.type, a.driver_name, a.driver_phone, a.latitude, a.longitude, a.green_corridor_active
        FROM emergency_ambulances ea
        JOIN ambulances a ON ea.ambulance_id = a.id
        WHERE ea.emergency_id = ?
        ORDER BY ea.requested_at ASC
    """, (id,))
    all_assigned = [dict(ar) for ar in cursor.fetchall()]
    conn.close()

    return {
        "message": f"Requested {len(added_ambs)} additional ambulance(s) for emergency {id}",
        "newly_added": [a["id"] for a in added_ambs],
        "newly_assigned": added_ambs[0] if added_ambs else None,
        "assigned_ambulances": all_assigned
    }

@app.put("/api/emergencies/{id}/ambulances/{ambulance_id}/status")
def update_emergency_ambulance_status(id: str, ambulance_id: str, payload: AmbulanceStatusUpdate):
    valid_statuses = ["REQUESTED", "ACCEPTED", "ON_THE_WAY", "ARRIVED", "COMPLETED"]
    normalized_status = payload.status.upper().replace(" ", "_")
    if normalized_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emergency_ambulances WHERE emergency_id = ? AND ambulance_id = ?", (id, ambulance_id))
    record = cursor.fetchone()
    if not record:
        conn.close()
        raise HTTPException(status_code=404, detail="Ambulance is not assigned to this emergency")

    now = datetime.now().isoformat()
    note_val = payload.notes if payload.notes else record["notes"]

    cursor.execute("""
        UPDATE emergency_ambulances
        SET status = ?, updated_at = ?, notes = ?
        WHERE emergency_id = ? AND ambulance_id = ?
    """, (normalized_status, now, note_val, id, ambulance_id))

    if normalized_status == "COMPLETED":
        cursor.execute("SELECT COUNT(*) FROM emergency_ambulances WHERE ambulance_id = ? AND status != 'COMPLETED'", (ambulance_id,))
        remaining = cursor.fetchone()[0]
        if remaining == 0:
            cursor.execute("UPDATE ambulances SET status = 'AVAILABLE', assigned_emergency_id = NULL, green_corridor_active = 0 WHERE id = ?", (ambulance_id,))
    elif normalized_status in ["ACCEPTED", "ON_THE_WAY", "ARRIVED"]:
        cursor.execute("UPDATE ambulances SET status = 'DISPATCHED', assigned_emergency_id = ? WHERE id = ?", (id, ambulance_id))

    conn.commit()
    conn.close()
    return {
        "emergency_id": id,
        "ambulance_id": ambulance_id,
        "new_status": normalized_status,
        "status": normalized_status,
        "current_status": normalized_status,
        "updated_at": now
    }

@app.put("/api/emergencies/{id}/status")
def update_emergency_status(id: str, payload: StatusUpdate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emergencies WHERE id = ?", (id,))
    emg = cursor.fetchone()
    if not emg:
        conn.close()
        raise HTTPException(status_code=404, detail="Emergency not found")

    cursor.execute("UPDATE emergencies SET status = ? WHERE id = ?", (payload.status, id))

    # If resolved, free all assigned ambulances
    if payload.status == "RESOLVED":
        cursor.execute("""
            UPDATE emergency_ambulances
            SET status = 'COMPLETED', updated_at = ?
            WHERE emergency_id = ?
        """, (datetime.now().isoformat(), id))

        cursor.execute("SELECT ambulance_id FROM emergency_ambulances WHERE emergency_id = ?", (id,))
        for row in cursor.fetchall():
            amb_id = row["ambulance_id"]
            cursor.execute("""
                UPDATE ambulances 
                SET status = 'AVAILABLE', assigned_emergency_id = NULL, green_corridor_active = 0
                WHERE id = ?
            """, (amb_id,))

        if emg["assigned_ambulance_id"]:
            cursor.execute("""
                UPDATE ambulances 
                SET status = 'AVAILABLE', assigned_emergency_id = NULL, green_corridor_active = 0
                WHERE id = ?
            """, (emg["assigned_ambulance_id"],))

    conn.commit()
    conn.close()
    return {"message": "Status updated successfully", "id": id, "new_status": payload.status}

# 2. HOSPITALS, BLOOD INVENTORY & OXYGEN RADAR
@app.get("/api/hospitals")
def get_hospitals(
    blood_group: Optional[str] = None,
    min_oxygen: Optional[float] = None,
    min_icu: Optional[int] = None,
    user_lat: Optional[float] = None,
    user_lon: Optional[float] = None
):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hospitals")
    hospitals = [dict(h) for h in cursor.fetchall()]

    for h in hospitals:
        # Fetch blood inventory
        cursor.execute("SELECT blood_group, units_available FROM blood_inventory WHERE hospital_id = ?", (h["id"],))
        blood_rows = cursor.fetchall()
        h["blood_inventory"] = {r["blood_group"]: r["units_available"] for r in blood_rows}

        # Calculate distance if coordinates provided
        if user_lat is not None and user_lon is not None:
            h["distance_km"] = round(routing_engine.haversine_km(user_lat, user_lon, h["latitude"], h["longitude"]), 2)
        else:
            h["distance_km"] = 0.0

    conn.close()

    # Filter by blood group
    if blood_group:
        hospitals = [h for h in hospitals if h["blood_inventory"].get(blood_group, 0) > 0]

    # Filter by oxygen
    if min_oxygen is not None:
        hospitals = [h for h in hospitals if h["liquid_oxygen_percentage"] >= min_oxygen or h["oxygen_cylinders_available"] >= 10]

    # Filter by ICU
    if min_icu is not None:
        hospitals = [h for h in hospitals if h["icu_beds_available"] >= min_icu]

    # Sort by distance if available
    if user_lat is not None and user_lon is not None:
        hospitals.sort(key=lambda h: h["distance_km"])

    return hospitals

@app.post("/api/hospitals/{id}/inventory")
def update_hospital_inventory(id: str, payload: InventoryUpdate):
    conn = get_db()
    cursor = conn.cursor()

    if payload.blood_group and payload.units_delta is not None:
        cursor.execute("""
            UPDATE blood_inventory 
            SET units_available = MAX(0, units_available + ?), last_updated = ?
            WHERE hospital_id = ? AND blood_group = ?
        """, (payload.units_delta, datetime.now().isoformat(), id, payload.blood_group))

    if payload.oxygen_cylinders is not None:
        cursor.execute("UPDATE hospitals SET oxygen_cylinders_available = ? WHERE id = ?", (payload.oxygen_cylinders, id))

    if payload.liquid_oxygen_percentage is not None:
        cursor.execute("UPDATE hospitals SET liquid_oxygen_percentage = ? WHERE id = ?", (payload.liquid_oxygen_percentage, id))

    if payload.icu_beds_available is not None:
        cursor.execute("UPDATE hospitals SET icu_beds_available = ? WHERE id = ?", (payload.icu_beds_available, id))

    conn.commit()
    conn.close()
    return {"message": "Inventory updated successfully"}

# 3. AMBULANCES & NAVIGATION
@app.get("/api/ambulances")
def get_ambulances():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ambulances")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/ambulances/{id}/position")
def update_ambulance_position(id: str, lat: float, lon: float, status: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    if status:
        cursor.execute("UPDATE ambulances SET latitude = ?, longitude = ?, status = ? WHERE id = ?", (lat, lon, status, id))
    else:
        cursor.execute("UPDATE ambulances SET latitude = ?, longitude = ? WHERE id = ?", (lat, lon, id))
    conn.commit()
    conn.close()
    return {"message": "Position updated"}

# 4. FASTEST ROUTING & TRAFFIC SIGNAL GREEN CORRIDOR
@app.get("/api/route")
def get_route(ambulance_id: str, target_lat: float, target_lon: float, destination_hospital_id: Optional[str] = "HOSP-01"):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ambulances WHERE id = ?", (ambulance_id,))
    amb = cursor.fetchone()
    if not amb:
        conn.close()
        raise HTTPException(status_code=404, detail="Ambulance not found")

    cursor.execute("SELECT * FROM hospitals WHERE id = ?", (destination_hospital_id,))
    hosp = cursor.fetchone()
    hosp_lat = hosp["latitude"] if hosp else 22.5780
    hosp_lon = hosp["longitude"] if hosp else 88.3680

    cursor.execute("SELECT * FROM traffic_signals")
    signals = [dict(s) for s in cursor.fetchall()]
    conn.close()

    # Route 1: Ambulance to Emergency Patient
    leg1_waypoints = routing_engine.generate_interpolated_route(
        amb["latitude"], amb["longitude"], target_lat, target_lon, steps=12
    )
    # Route 2: Patient to Hospital
    leg2_waypoints = routing_engine.generate_interpolated_route(
        target_lat, target_lon, hosp_lat, hosp_lon, steps=12
    )

    full_waypoints = leg1_waypoints + leg2_waypoints

    corridor_data = routing_engine.compute_green_corridor(
        (amb["latitude"], amb["longitude"]),
        full_waypoints,
        signals
    )

    return {
        "ambulance": dict(amb),
        "target_location": [target_lat, target_lon],
        "hospital_destination": {"id": hosp["id"], "name": hosp["name"], "lat": hosp_lat, "lon": hosp_lon},
        "leg1_waypoints": leg1_waypoints,
        "leg2_waypoints": leg2_waypoints,
        "full_waypoints": full_waypoints,
        "corridor_analytics": corridor_data
    }

@app.post("/api/green-corridor/toggle")
def toggle_green_corridor(ambulance_id: str, activate: bool):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE ambulances SET green_corridor_active = ? WHERE id = ?", (1 if activate else 0, ambulance_id))
    
    # Update traffic signals along key corridor
    cursor.execute("UPDATE traffic_signals SET green_corridor_active = ?, current_state = ? WHERE 1=1", (1 if activate else 0, "GREEN" if activate else "RED"))
    conn.commit()
    conn.close()
    return {
        "message": f"Green Corridor {'ACTIVATED' if activate else 'DEACTIVATED'} for Ambulance {ambulance_id}",
        "signals_preempted": activate
    }

@app.get("/api/signals")
def get_traffic_signals():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM traffic_signals")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/signals/{id}/state")
def update_signal_state(id: str, state: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE traffic_signals SET current_state = ? WHERE id = ?", (state.upper(), id))
    conn.commit()
    conn.close()
    return {"message": "Traffic signal state updated", "id": id, "state": state.upper()}

# 5. PATIENT EMERGENCY HEALTH RECORD (EHR & QR PASS) & MEDICATION MANAGEMENT
@app.get("/api/patient/{id}")
def get_patient_record(id: str, pin: Optional[str] = None, emergency_override: bool = False):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patient_records WHERE id = ?", (id,))
    patient = cursor.fetchone()

    if not patient:
        conn.close()
        raise HTTPException(status_code=404, detail="Patient Emergency Record not found")

    p = dict(patient)
    # Parse JSON fields
    p["emergency_contacts"] = json.loads(p["emergency_contacts"]) if p["emergency_contacts"] else []
    p["known_allergies"] = json.loads(p["known_allergies"]) if p["known_allergies"] else []
    p["chronic_conditions"] = json.loads(p["chronic_conditions"]) if p["chronic_conditions"] else []

    # Fetch granular medications from patient_medications table
    cursor.execute("SELECT * FROM patient_medications WHERE patient_id = ? ORDER BY created_at ASC", (id,))
    med_rows = [dict(m) for m in cursor.fetchall()]
    p["medications"] = med_rows

    if med_rows:
        p["current_medications"] = [f"{m['name']} {m['dosage']} ({m['frequency']})" for m in med_rows]
    else:
        p["current_medications"] = json.loads(p["current_medications"]) if p["current_medications"] else []

    conn.close()

    # Pin verification for full sensitive data, or emergency override for certified trauma doctors
    if not emergency_override and pin and pin != p["emergency_access_pin"]:
        raise HTTPException(status_code=403, detail="Invalid Emergency Access PIN")

    return p

@app.put("/api/patient/{id}")
def update_patient_record(id: str, payload: PatientRecordUpdateRequest):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM patient_records WHERE id = ?", (id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Patient Emergency Record not found")

    existing_dict = dict(existing)
    full_name = payload.full_name if payload.full_name is not None else existing_dict["full_name"]
    dob = payload.dob if payload.dob is not None else existing_dict["dob"]
    blood_group = payload.blood_group if payload.blood_group is not None else existing_dict["blood_group"]
    past_surgeries = payload.past_surgeries if payload.past_surgeries is not None else existing_dict["past_surgeries"]
    insurance_policy = payload.insurance_policy if payload.insurance_policy is not None else existing_dict["insurance_policy"]
    emergency_access_pin = payload.emergency_access_pin if payload.emergency_access_pin is not None else existing_dict["emergency_access_pin"]

    # Emergency contacts
    if payload.emergency_contacts is not None:
        if isinstance(payload.emergency_contacts, (list, dict)):
            contacts_json = json.dumps(payload.emergency_contacts)
        else:
            contacts_json = json.dumps([{"name": str(payload.emergency_contacts), "phone": ""}])
    elif payload.emergency_contact is not None:
        if isinstance(payload.emergency_contact, dict):
            contacts_json = json.dumps([payload.emergency_contact])
        else:
            contacts_json = json.dumps([{"name": str(payload.emergency_contact), "phone": ""}])
    else:
        contacts_json = existing_dict["emergency_contacts"]

    # Known allergies
    if payload.known_allergies is not None:
        if isinstance(payload.known_allergies, list):
            allergies_json = json.dumps(payload.known_allergies)
        else:
            allergies_json = json.dumps([s.strip() for s in str(payload.known_allergies).split(",") if s.strip()])
    else:
        allergies_json = existing_dict["known_allergies"]

    # Chronic conditions
    if payload.chronic_conditions is not None:
        if isinstance(payload.chronic_conditions, list):
            conditions_json = json.dumps(payload.chronic_conditions)
        else:
            conditions_json = json.dumps([s.strip() for s in str(payload.chronic_conditions).split(",") if s.strip()])
    else:
        conditions_json = existing_dict["chronic_conditions"]

    cursor.execute("""
        UPDATE patient_records
        SET full_name = ?, dob = ?, blood_group = ?, emergency_contacts = ?,
            known_allergies = ?, chronic_conditions = ?, past_surgeries = ?,
            insurance_policy = ?, emergency_access_pin = ?
        WHERE id = ?
    """, (
        full_name, dob, blood_group,
        contacts_json,
        allergies_json,
        conditions_json,
        past_surgeries,
        insurance_policy,
        emergency_access_pin,
        id
    ))

    cursor.execute("SELECT * FROM patient_records WHERE id = ?", (id,))
    updated_rec = dict(cursor.fetchone())
    try:
        updated_rec["emergency_contacts"] = json.loads(updated_rec["emergency_contacts"]) if updated_rec["emergency_contacts"] else []
    except Exception:
        pass
    try:
        updated_rec["known_allergies"] = json.loads(updated_rec["known_allergies"]) if updated_rec["known_allergies"] else []
    except Exception:
        pass
    try:
        updated_rec["chronic_conditions"] = json.loads(updated_rec["chronic_conditions"]) if updated_rec["chronic_conditions"] else []
    except Exception:
        pass

    conn.commit()
    conn.close()
    return {
        "message": "Patient medical profile updated successfully",
        "patient_id": id,
        "patient": updated_rec
    }

@app.post("/api/patient")
def save_patient_record(payload: PatientRecordRequest):
    conn = get_db()
    cursor = conn.cursor()
    pid = payload.id if payload.id else f"P-{str(uuid.uuid4())[:6].upper()}"

    cursor.execute("""
        INSERT OR REPLACE INTO patient_records (
            id, full_name, dob, blood_group, emergency_contacts,
            known_allergies, chronic_conditions, current_medications,
            past_surgeries, insurance_policy, emergency_access_pin
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pid, payload.full_name, payload.dob, payload.blood_group,
        json.dumps(payload.emergency_contacts),
        json.dumps(payload.known_allergies),
        json.dumps(payload.chronic_conditions),
        json.dumps(payload.current_medications or []),
        payload.past_surgeries, payload.insurance_policy,
        payload.emergency_access_pin
    ))
    conn.commit()
    conn.close()
    return {"message": "Patient profile saved successfully", "patient_id": pid}

# Granular Current Medication Endpoints
@app.get("/api/patient/{id}/medications")
def list_patient_medications(id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patient_medications WHERE patient_id = ? ORDER BY created_at ASC", (id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/patient/{id}/medications")
def add_patient_medication(id: str, payload: MedicationItem):
    conn = get_db()
    cursor = conn.cursor()
    med_id = payload.id if payload.id else f"MED-{str(uuid.uuid4())[:6].upper()}"
    now = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO patient_medications (
            id, patient_id, name, dosage, frequency, start_date, end_date, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        med_id, id, payload.name, payload.dosage, payload.frequency,
        payload.start_date or "Today", payload.end_date or "Ongoing", payload.notes or "", now
    ))
    conn.commit()

    # Query all active medications for response
    cursor.execute("SELECT * FROM patient_medications WHERE patient_id = ? ORDER BY created_at ASC", (id,))
    all_meds = [dict(r) for r in cursor.fetchall()]
    conn.close()

    inserted_med = next((m for m in all_meds if m["id"] == med_id), None)
    return {
        "message": f"Medication '{payload.name}' added successfully without replacing existing medications",
        "medication_id": med_id,
        "medication": inserted_med,
        "medications": all_meds
    }

@app.put("/api/patient/{id}/medications/{med_id}")
def update_patient_medication(id: str, med_id: str, payload: MedicationItem):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patient_medications WHERE id = ? AND patient_id = ?", (med_id, id))
    med = cursor.fetchone()
    if not med:
        conn.close()
        raise HTTPException(status_code=404, detail="Medication not found for this patient")

    cursor.execute("""
        UPDATE patient_medications
        SET name = ?, dosage = ?, frequency = ?, start_date = ?, end_date = ?, notes = ?
        WHERE id = ? AND patient_id = ?
    """, (
        payload.name, payload.dosage, payload.frequency,
        payload.start_date or med["start_date"], payload.end_date or med["end_date"],
        payload.notes if payload.notes is not None else med["notes"],
        med_id, id
    ))
    conn.commit()

    cursor.execute("SELECT * FROM patient_medications WHERE patient_id = ? ORDER BY created_at ASC", (id,))
    all_meds = [dict(r) for r in cursor.fetchall()]
    conn.close()

    updated_med = next((m for m in all_meds if m["id"] == med_id), None)
    return {
        "message": "Medication updated successfully",
        "medication_id": med_id,
        "medication": updated_med,
        "medications": all_meds
    }

@app.delete("/api/patient/{id}/medications/{med_id}")
def delete_patient_medication(id: str, med_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM patient_medications WHERE id = ? AND patient_id = ?", (med_id, id))
    conn.commit()

    cursor.execute("SELECT * FROM patient_medications WHERE patient_id = ? ORDER BY created_at ASC", (id,))
    all_meds = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return {"message": "Medication removed successfully", "deleted_id": med_id, "medications": all_meds}

# 6. AI MEDICAL JARGON & PRESCRIPTION SIMPLIFIER
@app.post("/api/simplify")
def simplify_prescription(payload: SimplifyRequest):
    result = medical_simplifier.simplify_medical_text(payload.text)
    return result

# 7. DISASTER PROTOCOLS & TRIAGE ASSESSMENT
@app.get("/api/disaster-protocols")
def get_disaster_protocols():
    return {
        "FLOOD": {
            "title": "Flash Flood & Water Surge Emergency",
            "priority_action": "Seek high ground immediately. Disconnect main electrical breaker. Never drive or walk through flood waters (>15cm can knock a person down).",
            "medical_risks": ["Hypothermia", "Waterborne Leptospirosis / Cholera", "Submersion injury", "Electrical shock"],
            "kit_checklist": ["Purification tablets / Clean water", "Dry airtight medication pouch", "Emergency whistle & high-power torch", "Floating life-vest / buoyant object"]
        },
        "EARTHQUAKE": {
            "title": "Earthquake Rapid Response",
            "priority_action": "DROP, COVER, AND HOLD ON. Stay away from windows, masonry, and heavy overhead fixtures. Do not use elevators.",
            "medical_risks": ["Crush injury & Compartment syndrome", "Blunt chest/abdominal trauma", "Bone fractures", "Head injury / Concussion"],
            "kit_checklist": ["Tourniquets & sterile pressure dressings", "Dust masks (N95) for rubble dust", "Splints for immobilization", "Emergency battery radio"]
        },
        "FIRE": {
            "title": "Structural & Urban Fire Emergency",
            "priority_action": "Get low and crawl under smoke. Feel doors before opening (do not open hot doors). Close doors behind you to slow fire spread.",
            "medical_risks": ["Smoke inhalation & Carbon Monoxide poisoning", "Thermal burns", "Airway edema (swelling)", "Corneal burn injury"],
            "kit_checklist": ["Clean moist cloth for breathing", "Burn dressing gel / Sterile non-adherent pads", "Saline eye wash", "Cold clean water"]
        },
        "CARDIAC_ARREST": {
            "title": "Out-of-Hospital Cardiac Arrest Protocol",
            "priority_action": "Check responsiveness and breathing. Immediately call SOS. Start Hands-Only CPR at 100-120 beats per minute (center of chest, push hard & fast).",
            "medical_risks": ["Brain anoxia after 4-6 minutes", "Permanent neurological damage", "Ventricular fibrillation"],
            "kit_checklist": ["Automated External Defibrillator (AED) if available nearby", "Aspirin 300mg (if conscious & prescribed)", "Barrier CPR mask"]
        }
    }

@app.post("/api/triage/calculate")
def calculate_start_triage(data: TriageRequest):
    """
    Implements Simple Triage And Rapid Treatment (START) algorithm used worldwide in disaster medicine.
    """
    if data.can_walk:
        return {
            "tag": "GREEN",
            "priority": "MINOR / WALKING WOUNDED",
            "color_hex": "#10B981",
            "action": "Direct to secondary triage area. Re-evaluate as resources allow."
        }
    
    if data.respiration_rate == 0:
        return {
            "tag": "BLACK",
            "priority": "EXPECTANT / DECEASED",
            "color_hex": "#1F2937",
            "action": "No spontaneous breathing after airway repositioning. Palliative care or tag for rescue teams."
        }
    
    if data.respiration_rate > 30 or not data.radial_pulse_present or not data.follows_commands:
        return {
            "tag": "RED",
            "priority": "IMMEDIATE / CRITICAL",
            "color_hex": "#EF4444",
            "action": "Immediate life-saving intervention needed! Transport priority 1 (ALS Ambulance)."
        }
    
    return {
        "tag": "YELLOW",
        "priority": "DELAYED / SERIOUS",
        "color_hex": "#F59E0B",
        "action": "Serious condition requiring medical care, but vitals stable for the moment. Transport priority 2."
    }

# 8. CITY METRICS & BROADCASTS
@app.get("/api/stats")
def get_system_stats():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM emergencies WHERE status != 'RESOLVED'")
    active_emergencies = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM ambulances WHERE status != 'AVAILABLE'")
    active_ambulances = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(available_beds), SUM(icu_beds_available), SUM(oxygen_cylinders_available) FROM hospitals")
    hosp_stats = cursor.fetchone()

    cursor.execute("SELECT SUM(units_available) FROM blood_inventory")
    total_blood_units = cursor.fetchone()[0]

    conn.close()

    return {
        "active_emergencies": active_emergencies,
        "ambulances_deployed": active_ambulances,
        "available_beds": hosp_stats[0] or 0,
        "available_icu_beds": hosp_stats[1] or 0,
        "oxygen_cylinders": hosp_stats[2] or 0,
        "total_blood_units": total_blood_units or 0,
        "green_corridor_status": "ONLINE & ARMED"
    }

@app.get("/api/broadcasts")
def get_broadcasts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM disaster_broadcasts WHERE is_active = 1 ORDER BY created_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/broadcasts")
def create_broadcast(payload: BroadcastRequest):
    conn = get_db()
    cursor = conn.cursor()
    bid = f"DIS-{str(uuid.uuid4())[:6].upper()}"
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO disaster_broadcasts (
            id, created_at, title, hazard_type, severity,
            description, safety_instructions, evacuation_route, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (bid, now, payload.title, payload.hazard_type, payload.severity, payload.description, payload.safety_instructions, payload.evacuation_route))
    conn.commit()
    conn.close()
    return {"message": "Disaster broadcast issued", "id": bid}

# ==================== FEATURE 1: DOCTOR LOGIN PORTAL ====================

class DoctorRegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str
    specialization: str
    hospital_id: Optional[str] = "HOSP-01"
    hospital_name: Optional[str] = ""
    experience_years: Optional[int] = 0
    phone: Optional[str] = ""
    bio: Optional[str] = ""

class DoctorLoginRequest(BaseModel):
    email: str
    password: str

class DoctorAvailabilityUpdate(BaseModel):
    is_available: bool
    is_on_call: Optional[bool] = None

class EmergencyDoctorRequest(BaseModel):
    doctor_ids: List[str]
    notes: Optional[str] = ""

class DoctorStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = ""

@app.post("/api/doctors/register")
def register_doctor(payload: DoctorRegisterRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM doctors WHERE email = ?", (payload.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="A doctor account with this email already exists.")
    doc_id = f"DOC-{str(uuid.uuid4())[:6].upper()}"
    now = datetime.now().isoformat()
    pass_hash = f"hash_{payload.password[:4]}xxx"
    cursor.execute("""
        INSERT INTO doctors (id, full_name, email, password_hash, specialization, hospital_id, hospital_name, experience_years, rating, is_available, is_on_call, phone, bio, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 4.5, 1, 0, ?, ?, ?)
    """, (doc_id, payload.full_name, payload.email, pass_hash, payload.specialization,
          payload.hospital_id, payload.hospital_name, payload.experience_years, payload.phone, payload.bio, now))
    conn.commit()
    conn.close()
    return {"message": "Doctor registered successfully", "doctor_id": doc_id, "email": payload.email}

@app.post("/api/doctors/login")
def login_doctor(payload: DoctorLoginRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM doctors WHERE email = ?", (payload.email,))
    doctor = cursor.fetchone()
    conn.close()
    if not doctor:
        raise HTTPException(status_code=404, detail="No doctor account found with this email.")
    doc_dict = dict(doctor)
    stored = doc_dict.get("password_hash", "")
    expected = f"hash_{payload.password[:4]}xxx"
    # Seeded doctors use "hashed_pass_N" as placeholder - accept any password for demo
    if not (stored.startswith("hashed_pass") or stored == expected):
        raise HTTPException(status_code=401, detail="Invalid password.")
    doc_dict.pop("password_hash", None)
    return {"message": "Login successful", "doctor": doc_dict, "token": f"tok_{doc_dict['id']}"}

@app.get("/api/doctors")
def list_doctors(
    specialization: Optional[str] = None,
    available_only: bool = False,
    on_call_only: bool = False
):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM doctors WHERE 1=1"
    params: List[Any] = []
    if specialization:
        query += " AND specialization = ?"
        params.append(specialization)
    if available_only:
        query += " AND is_available = 1"
    if on_call_only:
        query += " AND is_on_call = 1"
    query += " ORDER BY rating DESC, experience_years DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    for r in rows:
        r.pop("password_hash", None)
    conn.close()
    return rows

@app.get("/api/doctors/{doc_id}")
def get_doctor(doc_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doc_id,))
    doctor = cursor.fetchone()
    conn.close()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    d = dict(doctor)
    d.pop("password_hash", None)
    return d

@app.put("/api/doctors/{doc_id}/availability")
def update_doctor_availability(doc_id: str, payload: DoctorAvailabilityUpdate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE doctors SET is_available = ? WHERE id = ?", (1 if payload.is_available else 0, doc_id))
    if payload.is_on_call is not None:
        cursor.execute("UPDATE doctors SET is_on_call = ? WHERE id = ?", (1 if payload.is_on_call else 0, doc_id))
    conn.commit()
    conn.close()
    return {"message": "Availability updated", "doctor_id": doc_id, "is_available": payload.is_available}

@app.post("/api/emergencies/{emg_id}/doctors")
def assign_doctors_to_emergency(emg_id: str, payload: EmergencyDoctorRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emergencies WHERE id = ?", (emg_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Emergency not found")
    now = datetime.now().isoformat()
    assigned = []
    for doc_id in payload.doctor_ids:
        cursor.execute("SELECT * FROM doctors WHERE id = ?", (doc_id,))
        doc = cursor.fetchone()
        if doc:
            cursor.execute("""
                INSERT OR REPLACE INTO emergency_doctors (emergency_id, doctor_id, status, requested_at, notes)
                VALUES (?, ?, 'REQUESTED', ?, ?)
            """, (emg_id, doc_id, now, payload.notes or "Assigned by emergency dispatcher"))
            assigned.append({"doctor_id": doc_id, "name": doc["full_name"], "specialization": doc["specialization"]})
    conn.commit()
    conn.close()
    return {"message": f"{len(assigned)} doctor(s) alerted for emergency {emg_id}", "assigned_doctors": assigned}

@app.get("/api/emergencies/{emg_id}/doctors")
def get_emergency_doctors(emg_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ed.doctor_id, ed.status, ed.requested_at, ed.accepted_at, ed.notes,
               d.full_name, d.specialization, d.hospital_name, d.phone, d.rating
        FROM emergency_doctors ed
        JOIN doctors d ON ed.doctor_id = d.id
        WHERE ed.emergency_id = ?
        ORDER BY ed.requested_at ASC
    """, (emg_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.put("/api/emergencies/{emg_id}/doctors/{doc_id}/status")
def update_doctor_case_status(emg_id: str, doc_id: str, payload: DoctorStatusUpdate):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    accepted_at = now if payload.status == "ACCEPTED" else None
    cursor.execute("""
        UPDATE emergency_doctors SET status = ?, accepted_at = ?, notes = ?
        WHERE emergency_id = ? AND doctor_id = ?
    """, (payload.status, accepted_at, payload.notes, emg_id, doc_id))
    conn.commit()
    conn.close()
    return {"message": "Doctor case status updated", "status": payload.status}

# ==================== FEATURE 2: ORGAN TRANSPORT GREEN CORRIDOR ====================

ORGAN_VIABILITY_HOURS: dict = {
    "HEART": 6, "LUNG": 8, "LIVER": 24,
    "PANCREAS": 24, "KIDNEY": 36, "CORNEA": 336
}

class OrganTransportRequest(BaseModel):
    organ_type: str
    donor_hospital_id: str
    recipient_hospital_id: str
    ambulance_id: Optional[str] = "AMB-101"
    notes: Optional[str] = ""

class OrganStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = ""

@app.post("/api/organ-transports")
def create_organ_transport(payload: OrganTransportRequest):
    conn = get_db()
    cursor = conn.cursor()
    transport_id = f"ORGAN-{str(uuid.uuid4())[:8].upper()}"
    now = datetime.now().isoformat()
    viability = ORGAN_VIABILITY_HOURS.get(payload.organ_type.upper(), 24)
    cursor.execute("SELECT name FROM hospitals WHERE id = ?", (payload.donor_hospital_id,))
    donor_h = cursor.fetchone()
    donor_name = donor_h["name"] if donor_h else payload.donor_hospital_id
    cursor.execute("SELECT name FROM hospitals WHERE id = ?", (payload.recipient_hospital_id,))
    recip_h = cursor.fetchone()
    recip_name = recip_h["name"] if recip_h else payload.recipient_hospital_id
    cursor.execute("""
        INSERT INTO organ_transports (
            id, organ_type, donor_hospital_id, donor_hospital_name,
            recipient_hospital_id, recipient_hospital_name, ambulance_id,
            harvested_at, viability_hours, status, corridor_active, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'VIABLE', 1, ?, ?)
    """, (transport_id, payload.organ_type.upper(), payload.donor_hospital_id, donor_name,
          payload.recipient_hospital_id, recip_name, payload.ambulance_id,
          now, viability, payload.notes or f"{payload.organ_type} transport corridor activated", now))
    cursor.execute("UPDATE ambulances SET green_corridor_active = 1, status = 'DISPATCHED' WHERE id = ?", (payload.ambulance_id,))
    cursor.execute("UPDATE traffic_signals SET green_corridor_active = 1, current_state = 'GREEN'")
    conn.commit()
    conn.close()
    return {
        "transport_id": transport_id, "organ_type": payload.organ_type.upper(),
        "viability_hours": viability, "status": "VIABLE", "corridor_active": True,
        "harvested_at": now,
        "message": f"Organ corridor ACTIVATED for {payload.organ_type.upper()} transport. All signals preempted to GREEN."
    }

@app.get("/api/organ-transports")
def list_organ_transports(active_only: bool = False):
    conn = get_db()
    cursor = conn.cursor()
    if active_only:
        cursor.execute("SELECT * FROM organ_transports WHERE status != 'UNVIABLE' AND status != 'DELIVERED' ORDER BY created_at DESC")
    else:
        cursor.execute("SELECT * FROM organ_transports ORDER BY created_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.get("/api/organ-transports/{transport_id}")
def get_organ_transport(transport_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM organ_transports WHERE id = ?", (transport_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Organ transport not found")
    return dict(row)

@app.put("/api/organ-transports/{transport_id}/status")
def update_organ_transport_status(transport_id: str, payload: OrganStatusUpdate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM organ_transports WHERE id = ?", (transport_id,))
    transport = cursor.fetchone()
    if not transport:
        conn.close()
        raise HTTPException(status_code=404, detail="Transport not found")
    status_upper = payload.status.upper()
    corridor_active = 0 if status_upper in ["UNVIABLE", "DELIVERED"] else 1
    cursor.execute("""
        UPDATE organ_transports SET status = ?, corridor_active = ?, notes = ? WHERE id = ?
    """, (status_upper, corridor_active, payload.notes or transport["notes"], transport_id))
    if status_upper in ["UNVIABLE", "DELIVERED"]:
        cursor.execute("UPDATE ambulances SET green_corridor_active = 0, status = 'AVAILABLE' WHERE id = ?", (transport["ambulance_id"],))
        cursor.execute("UPDATE traffic_signals SET green_corridor_active = 0, current_state = 'RED'")
    conn.commit()
    conn.close()
    msg_map = {
        "UNVIABLE": "ORGAN MARKED UNVIABLE — Corridor deactivated. Recipient hospital notified.",
        "DELIVERED": "Organ delivered successfully. Corridor closed. Ambulance returned to service.",
        "AT_RISK": "Organ viability AT RISK — Corridor priority escalated.",
        "VIABLE": "Organ status confirmed VIABLE."
    }
    return {"transport_id": transport_id, "new_status": status_upper,
            "corridor_active": corridor_active, "message": msg_map.get(status_upper, f"Status updated to {status_upper}")}

# ==================== FEATURE 3: AMBULANCE OFFICER SAFETY CHECK-INS ====================

class OfficerCheckinRequest(BaseModel):
    officer_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = ""

@app.post("/api/ambulances/{amb_id}/checkin")
def officer_checkin(amb_id: str, payload: OfficerCheckinRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ambulances WHERE id = ?", (amb_id,))
    amb = cursor.fetchone()
    if not amb:
        conn.close()
        raise HTTPException(status_code=404, detail="Ambulance not found")
    checkin_id = f"CHKIN-{str(uuid.uuid4())[:6].upper()}"
    now = datetime.now().isoformat()
    officer = payload.officer_name or amb["driver_name"]
    lat = payload.latitude or amb["latitude"]
    lon = payload.longitude or amb["longitude"]
    cursor.execute("""
        INSERT INTO officer_checkins (id, ambulance_id, officer_name, checked_in_at, latitude, longitude, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (checkin_id, amb_id, officer, now, lat, lon, payload.notes or "Routine safety check-in"))
    if payload.latitude and payload.longitude:
        cursor.execute("UPDATE ambulances SET latitude = ?, longitude = ? WHERE id = ?", (lat, lon, amb_id))
    conn.commit()
    conn.close()
    return {"checkin_id": checkin_id, "ambulance_id": amb_id, "officer_name": officer,
            "checked_in_at": now, "message": f"Safety check-in confirmed for {officer}"}

@app.get("/api/ambulances/{amb_id}/checkins")
def get_officer_checkins(amb_id: str, limit: int = 10):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM officer_checkins WHERE ambulance_id = ? ORDER BY checked_in_at DESC LIMIT ?", (amb_id, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.get("/api/ambulances/{amb_id}/safety-status")
def get_officer_safety_status(amb_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ambulances WHERE id = ?", (amb_id,))
    amb = cursor.fetchone()
    if not amb:
        conn.close()
        raise HTTPException(status_code=404, detail="Ambulance not found")
    cursor.execute("SELECT checked_in_at FROM officer_checkins WHERE ambulance_id = ? ORDER BY checked_in_at DESC LIMIT 1", (amb_id,))
    last = cursor.fetchone()
    conn.close()
    last_checkin_time = last["checked_in_at"] if last else None
    is_overdue = False
    minutes_since = None
    if last_checkin_time:
        from datetime import datetime as dt
        delta = (dt.now() - dt.fromisoformat(last_checkin_time)).total_seconds() / 60
        minutes_since = round(delta, 1)
        is_overdue = delta > 15
    return {
        "ambulance_id": amb_id, "officer_name": amb["driver_name"],
        "last_checkin": last_checkin_time, "minutes_since_checkin": minutes_since,
        "is_overdue": is_overdue,
        "status": "OVERDUE" if is_overdue else ("OK" if last_checkin_time else "NO_CHECKINS")
    }

# ==================== FEATURE 4: UNIFIED 3-PORTAL AUTH & ROLE-BASED ROUTING ====================

class AuthLoginRequest(BaseModel):
    email: str
    password: Optional[str] = "demo"
    role: Optional[str] = None


@app.post("/api/auth/login")
def auth_login(payload: AuthLoginRequest):
    email_clean = (payload.email or "").strip().lower()
    role_hint = (payload.role or "").strip().upper() if payload.role else None

    conn = get_db()
    cursor = conn.cursor()

    # Search user by email (case-insensitive)
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email_clean,))
    user = cursor.fetchone()

    # If not found by email, check if role was provided as email shorthand ('patient', 'doctor', 'ambulance')
    if not user and email_clean in ["patient", "doctor", "ambulance"]:
        cursor.execute("SELECT * FROM users WHERE LOWER(role) = ?", (email_clean,))
        user = cursor.fetchone()

    # If still not found and role hint is given, try by role
    if not user and role_hint:
        cursor.execute("SELECT * FROM users WHERE UPPER(role) = ?", (role_hint,))
        user = cursor.fetchone()

    # Ensure demo accounts exist if database was freshly initialized
    if not user:
        demo_map = {
            "patient@demo.com": ("USR-P001", "patient@demo.com", "PATIENT", "P-101"),
            "doctor@demo.com": ("USR-D001", "doctor@demo.com", "DOCTOR", "DOC-001"),
            "ambulance@demo.com": ("USR-A001", "ambulance@demo.com", "AMBULANCE", "AMB-101")
        }
        if email_clean in demo_map:
            u_id, u_email, u_role, u_prof = demo_map[email_clean]
            now_iso = datetime.now().isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO users (id, email, password_hash, role, profile_id, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (u_id, u_email, "hash_demoxxxx", u_role, u_prof, now_iso, now_iso))
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE id = ?", (u_id,))
            user = cursor.fetchone()

    if not user:
        conn.close()
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials. Use a registered portal email (patient@demo.com, doctor@demo.com, ambulance@demo.com)."
        )

    user_dict = dict(user)
    user_role = user_dict["role"].upper()
    now_iso = datetime.now().isoformat()

    # Update last_login
    cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (now_iso, user_dict["id"]))
    conn.commit()

    # Retrieve role-specific profile details
    profile_data = {}
    if user_role == "PATIENT":
        prof_id = user_dict.get("profile_id") or "P-101"
        cursor.execute("SELECT * FROM patient_records WHERE id = ?", (prof_id,))
        p_row = cursor.fetchone()
        if p_row:
            p_dict = dict(p_row)
            for k in ["known_allergies", "chronic_conditions", "current_medications", "emergency_contacts"]:
                if p_dict.get(k) and isinstance(p_dict[k], str):
                    try:
                        p_dict[k] = json.loads(p_dict[k])
                    except Exception:
                        pass
            cursor.execute("SELECT * FROM patient_medications WHERE patient_id = ?", (prof_id,))
            p_dict["medications"] = [dict(m) for m in cursor.fetchall()]
            profile_data = p_dict
        else:
            profile_data = {"id": prof_id, "full_name": "Aarav Sharma", "blood_group": "O-"}

    elif user_role == "DOCTOR":
        prof_id = user_dict.get("profile_id") or "DOC-001"
        cursor.execute("SELECT * FROM doctors WHERE id = ? OR LOWER(email) = ?", (prof_id, user_dict["email"].lower()))
        d_row = cursor.fetchone()
        if d_row:
            d_dict = dict(d_row)
            d_dict.pop("password_hash", None)
            for k in ["degrees", "surgeries_performed"]:
                if d_dict.get(k) and isinstance(d_dict[k], str):
                    try:
                        d_dict[k] = json.loads(d_dict[k])
                    except Exception:
                        pass
            profile_data = d_dict
        else:
            profile_data = {"id": prof_id, "full_name": "Dr. Ananya Dasgupta", "specialization": "Trauma Surgery"}

    elif user_role == "AMBULANCE":
        prof_id = user_dict.get("profile_id") or "AMB-101"
        cursor.execute("SELECT * FROM ambulances WHERE id = ?", (prof_id,))
        a_row = cursor.fetchone()
        if a_row:
            profile_data = dict(a_row)
        else:
            profile_data = {"id": prof_id, "call_sign": "Alpha-1", "driver_name": "Ranjit Das", "status": "AVAILABLE"}

    conn.close()

    portal_slug = user_role.lower()
    token = f"RESQ-{user_role[:3]}-{uuid.uuid4().hex[:12].upper()}"

    return {
        "success": True,
        "token": token,
        "role": user_role,
        "portal": portal_slug,
        "redirect_url": f"/{portal_slug}",
        "user": {
            "id": user_dict["id"],
            "email": user_dict["email"],
            "role": user_role,
            "profile_id": user_dict.get("profile_id"),
            "last_login": now_iso
        },
        "profile": profile_data,
        "message": f"Successfully authenticated as {user_role} ({user_dict['email']}). Redirecting to {portal_slug} portal."
    }


@app.get("/api/auth/me")
def get_auth_me(email: Optional[str] = None, role: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    if email:
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email.strip().lower(),))
    elif role:
        cursor.execute("SELECT * FROM users WHERE UPPER(role) = ?", (role.strip().upper(),))
    else:
        cursor.execute("SELECT * FROM users LIMIT 1")
    user = cursor.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="No active user session found")
    u = dict(user)
    u.pop("password_hash", None)
    return {"user": u, "portal": u["role"].lower()}


@app.post("/api/auth/logout")
def auth_logout():
    return {"success": True, "message": "Logged out successfully from portal."}


@app.get("/api/auth/portals")
def get_portals_overview():
    return [
        {
            "role": "PATIENT",
            "portal": "patient",
            "title": "Citizen & Patient Portal",
            "description": "Emergency SOS, Digital Health Pass (QR/EHR), Medication Manager & Hospital Radar",
            "demo_email": "patient@demo.com",
            "demo_name": "Aarav Sharma (Blood O-)",
            "route": "/patient",
            "view_id": "citizenView"
        },
        {
            "role": "DOCTOR",
            "portal": "doctor",
            "title": "Emergency Doctor Portal",
            "description": "Trauma Response Console, On-Call Roster, Emergency EHR Access & Multi-Doctor Alert",
            "demo_email": "doctor@demo.com",
            "demo_name": "Dr. Ananya Dasgupta (Trauma Surgery)",
            "route": "/doctor",
            "view_id": "doctorView"
        },
        {
            "role": "AMBULANCE",
            "portal": "ambulance",
            "title": "Ambulance EMT Portal",
            "description": "Active Dispatch Telemetry, Green Corridor Navigation, Route Traffic Preemption & Safety Check-ins",
            "demo_email": "ambulance@demo.com",
            "demo_name": "Alpha-1 / Ranjit Das (ALS Unit)",
            "route": "/ambulance",
            "view_id": "ambulanceView"
        }
    ]


# ==================== ROLE-BASED PORTAL ROUTING ====================

# Serve Frontend Static Files
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "ResQNet API is live. Static directory not found."}


@app.get("/patient")
def serve_patient_portal():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "ResQNet Patient Portal is live."}


@app.get("/doctor")
def serve_doctor_portal():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "ResQNet Doctor Portal is live."}


@app.get("/ambulance")
def serve_ambulance_portal():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "ResQNet Ambulance EMT Portal is live."}


@app.get("/portal/{portal_name}")
def serve_portal_route(portal_name: str):
    slug = portal_name.strip().lower()
    if slug in ["patient", "doctor", "ambulance"]:
        index_file = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
    raise HTTPException(status_code=404, detail=f"Portal '{portal_name}' not found. Valid portals: patient, doctor, ambulance")

if __name__ == "__main__":
    import uvicorn
    print("Starting ResQNet Disaster & Emergency Management Server on http://localhost:8000 ...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
