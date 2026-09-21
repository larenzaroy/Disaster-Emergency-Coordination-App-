# Raksha ResQNet — Disaster \& Emergency Management System

> \*\*Connecting Patients, Hospitals, Doctors, Ambulances, and City Traffic Signals for Faster, Smarter Emergency Response.\*\*

**Raksha ResQNet** is an emergency-grade, real-time response platform designed to save lives during natural disasters (floods, earthquakes, fires) and critical medical crises (cardiac arrest, accidents, mass casualty incidents).

\---

## 🌟 Key Features

### 1\. 🚨 One-Tap SOS \& Multi-Ambulance Simultaneous Dispatch

* **One-Tap Trigger**: Instant emergency distress signal with an audible 3-second abort window to prevent accidental triggers.
* **Multiple Ambulances Simultaneously**:

  * Citizens and emergency responders can request multiple ambulances at once (`1 Ambulance`, `2 Ambulances`, or `3 Ambulances (Mass Casualty)`).
  * Can dispatch additional ambulances on-demand (`+1 More Ambulance`) to an active incident.
  * **Independent Ambulance Lifecycle**: Each assigned ambulance maintains its own real-time status:

    * 🟡 **REQUESTED** — Dispatch alert broadcasted to unit
    * 🔵 **ACCEPTED** — Paramedics acknowledged and preparing
    * 🟣 **ON THE WAY** — En route to incident with active navigation
    * 🟢 **ARRIVED AT SCENE** — Paramedics providing on-site care
    * ⚪ **COMPLETED** — Transport finished, unit returning to ready standby
  * **Separate Display**: Citizen active emergency view, EMT Dispatch Console, and Hospital ER Incoming Queue all display each assigned ambulance individually with real-time status badges and status update selectors.
* **Live GPS Tracking**: Automatically captures precise browser geolocation coordinates (`lat`, `lon`) and reverse-geocode addresses.
* **Audible Rescue Siren**: Built-in Web Audio API frequency-sweeping beacon synthesizer to help search-and-rescue teams locate victims trapped in rubble, floods, or collapsed buildings.
* **Visual Strobe Light**: Screen-flashing optical beacon for nighttime signaling to rescue boats or helicopters.

### 2\. 🪪 Editable Medical History \& Emergency Health Pass (QR / EHR)

* **Editable Medical History**:

  * Every user can add, edit, and update their personal medical history at any time through the **Edit History** portal.
  * Form allows updating: **Full Name**, **Date of Birth**, **Blood Group**, **Insurance Policy**, **Life-Threatening Allergies**, **Chronic Conditions**, **Past Surgeries**, and **Emergency Contacts**.
  * **Zero Data Loss**: Existing medical details remain permanently saved in SQLite unless explicitly edited or removed.
* **Emergency Health Pass (QR Code)**: Generates a high-density QR code readable on mobile devices.
* **Instant EHR Access**: Certified trauma doctors and EMTs can retrieve life-saving medical records without delays:

  * **Blood Group**
  * **Life-Threatening Allergies** (e.g. *Severe Penicillin Allergy*, *Latex Sensitivity*) prominently flagged in red alert banners.
  * **Chronic Conditions** (e.g. *Type 2 Diabetes*, *CAD with LAD Stent*, *Asthma*).
  * **Emergency Next-of-Kin Contacts** with 1-tap dial buttons.

### 3\. 💊 Current Medication Management (Granular \& Non-Overwriting)

* **Granular Medicine Records**: Dedicated section inside the user's medical profile for managing ongoing medications.
* **Detailed Fields**: Each medication record stores `name`, `dosage`, `frequency`, `start\_date`, `end\_date`, and `notes`.
* **Non-Overwriting Preservation**: Adding a new medication **never overwrites** existing medications. Adding Medicine A, then Medicine B, then Medicine C preserves all three simultaneously.
* **Full CRUD Capabilities**: Users can view all active medications, edit dosage or notes on the fly, and delete discontinued medicines individually.

### 4\. 🏥 Nearby Hospital \& Resource Radar (Blood \& Oxygen Inventory)

* **Live Hospital Directory**: Interactive Leaflet.js map and real-time capability cards.
* **Blood Bank Reserves**: Live breakdown of all 8 blood groups (**A+, A-, B+, B-, AB+, AB-, O+, O-**) with instant stock levels and low-stock alerts.
* **Medical Oxygen Availability**: Displays liquid oxygen manifold percentage (`%`) and reserve cylinder counts.
* **ICU \& Ventilator Bed Tracking**: Shows immediate trauma bed availability to avoid hospital diversions.
* **One-Click Direct Hotline \& Navigation**: Instantly calls hospital emergency trauma hotlines.

### 5\. 🚑 Smart Ambulance Routing \& Traffic Signal Green Corridor

* **Fastest Route Optimization**: Calculates turn-by-turn routing between Ambulance, Patient Incident, and Target Trauma Center.
* **Traffic Signal Preemption (Green Corridor)**:

  * Detects traffic intersections along the ambulance's path.
  * Automatically overrides signals from **RED** to **GREEN** as the ambulance approaches.
  * Displays dynamic analytics: **Estimated Time Saved (e.g., 5.6 minutes)** and priority ETA.
* **Live Driving Simulation**: Interactive map animation showing ambulance moving smoothly along the route while traffic lights turn green.
* **Pre-Hospital Telemetry**: EMTs can push patient vitals (**Blood Pressure, Pulse, SpO₂, Glasgow Coma Scale**) directly to the ER trauma bay before arrival.

### 6\. 📖 AI Medical Jargon \& Prescription Simplifier (Rx Decoder)

* **Plain Language Translation**: Translates doctor prescriptions, clinical abbreviations, and Latin dosage directions (`PO`, `TID`, `PC`, `STAT`, `PRN`, `NPO`) into simple, reassuring layman English.
* **Medication Guides**: Explains the exact generic name, clinical purpose, meal instructions, and critical side-effect warnings for common emergency drugs (*Augmentin, Paracetamol, Metformin, Amlodipine, Salbutamol, Aspirin, etc.*).
* **Clinical Jargon Dictionary**: Explains terms like *Dyspnea, Tachycardia, Cyanosis, Myocardial Infarction, Hypoxia, Rhonchi*.
* **Voice Read-Aloud (Text-to-Speech)**: Uses the browser Web Speech API to read the prescription explanation clearly aloud for stressed patients or visually impaired individuals.

### 7\. 🌊 Disaster Protocols \& START Triage Algorithm

* **Disaster Action Checklists**: Step-by-step emergency guides for **Floods**, **Earthquakes**, **Fires**, and **Out-of-Hospital Cardiac Arrest (CPR)**.
* **START Disaster Triage Calculator**:

  * Implements the worldwide *Simple Triage And Rapid Treatment* algorithm.
  * Evaluates: Can walk? Respiration rate? Radial pulse? Mental status?
  * Automatically assigns standard disaster color tags:

    * 🟩 **GREEN (Minor / Walking Wounded)**
    * 🟨 **YELLOW (Delayed / Serious)**
    * 🟥 **RED (Immediate / Critical — Life Threat)**
    * ⬛ **BLACK (Expectant / Deceased)**

\---

## 🏗️ System Architecture

```
ResQNet-Emergency-App/
├── database.py             # SQLite schemas (including emergency\_ambulances \& patient\_medications) \& seed data
├── main.py                 # FastAPI backend server with REST endpoints \& lifecycle controllers
├── routing\_engine.py       # Haversine distance, waypoint generation \& green corridor preemption
├── medical\_simplifier.py   # AI/NLP prescription parser, clinical jargon translator, and TTS engine
├── test\_api.py             # Automated test suite covering 11 functional domains
├── run.bat                 # 1-click Windows launcher (starts server \& opens browser)
├── README.md               # Complete project documentation
└── static/
    ├── index.html          # Unified Raksha command dashboard with modals and ambulance chips
    ├── styles.css          # Emergency dark theme with lifecycle badges and medication cards
    └── app.js              # Multi-ambulance dispatch, editable medical history, medication CRUD, maps \& speech
```

\---

## 🚀 Quick Start (Running the Project)

### Prerequisites

* Python 3.10+ (Verified running on Python 3.14 on Windows)
* Required packages: `fastapi`, `uvicorn`, `requests` (installed via pip)

### 1\. Launch with One Click

Simply double-click:

```bat
run.bat
```

This automatically launches the FastAPI server and opens `http://localhost:8000` in your default web browser.

### 2\. Or Launch via Command Line

```powershell
cd "c:\\Users\\akeya\\OneDrive\\Documents\\ResQNet-Emergency-App"
py main.py
```

Open your browser and navigate to:

```
http://localhost:8000
```

\---

## 🧪 Running Automated Tests

Run the comprehensive test suite to verify all endpoints and algorithms:

```powershell
py test\_api.py
```

**Expected Result:**

```
==================================================
RUNNING RAKSHA RESQNET COMPREHENSIVE ENDPOINT VERIFICATION
==================================================
Testing /api/health ...
  \[PASS] Health check OK
Testing /api/hospitals with blood \& oxygen filters ...
  \[PASS] Found 5 hospitals
  \[PASS] Filtered 5 hospitals with O- blood in stock
  \[PASS] Filtered 5 hospitals with high oxygen levels
Testing One-Tap SOS Dispatch /api/sos ...
  \[PASS] SOS Triggered: EMG-XXXX -> Assigned Amb: AMB-101, Hosp: Apollo Trauma Center
Testing Multiple Ambulances Simultaneous Dispatch \& Lifecycle ...
  \[PASS] Dispatched 2 ambulances simultaneously: \['AMB-102', 'AMB-101']
  \[PASS] Requested additional ambulance: AMB-103 (Total: 3)
  \[PASS] Independent status lifecycle verified across all assigned ambulances
Testing Ambulance Route \& Green Corridor /api/route ...
  \[PASS] Route Waypoints: 26, Normal ETA: 6.6m, Priority ETA: 1.0m (Saved 5.6m)
Testing Green Corridor Preemption Toggle ...
  \[PASS] Green corridor toggled successfully
Testing Doctor Emergency EHR Access /api/patient/P-101 ...
  \[PASS] Retrieved EHR for Aarav Sharma (Blood: O-, Allergies: \['Severe Penicillin Allergy', 'Peanuts'])
Testing Editable Medical History /api/patient/{id} ...
  \[PASS] Patient medical history updated successfully and verified via PUT response
  \[PASS] Persistent storage in SQLite verified via GET /api/patient/P-101
Testing Current Medication Management (Add, Retain without overwrite, Edit, Delete) ...
  \[PASS] Added Medicine A (Atorvastatin)
  \[PASS] Added Medicine B (Metformin)
  \[PASS] Added Medicine C (Vitamin D3)
  \[PASS] Verified non-overwriting behavior: All medications retained successfully!
  \[PASS] Edited Medicine B successfully to 1000mg
  \[PASS] Deleted Medicine C; Medicine A and updated Medicine B securely preserved.
Testing AI Prescription \& Jargon Simplifier /api/simplify ...
  \[PASS] Simplifier parsed 3 drugs, 4 jargon terms, and flagged allergy alert
Testing START Disaster Triage Calculator /api/triage/calculate ...
  \[PASS] Triage calculated RED tag for rapid breathing casualty
  \[PASS] Triage calculated GREEN tag for walking casualty
Testing System KPI Stats \& Broadcasts ...
  \[PASS] System Stats: Available Beds: 170, Total Blood Units: 638
==================================================
ALL 11 TEST SUITES PASSED FLAWLESSLY! 100% SUCCESS.
==================================================
```

