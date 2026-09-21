"""
ResQNet 2.0 - Database Layer
Three-portal system: Patient | Doctor | Ambulance
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resqnet.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        profile_id TEXT,
        created_at TEXT,
        last_login TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patient_records (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        full_name TEXT,
        age INTEGER,
        gender TEXT,
        dob TEXT,
        blood_group TEXT DEFAULT 'O+',
        known_allergies TEXT DEFAULT '[]',
        chronic_conditions TEXT DEFAULT '[]',
        current_medications TEXT DEFAULT '[]',
        past_surgeries TEXT DEFAULT '',
        emergency_contacts TEXT DEFAULT '[]',
        insurance_policy TEXT DEFAULT '',
        access_pin TEXT DEFAULT '1234',
        created_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patient_medications (
        id TEXT PRIMARY KEY,
        patient_id TEXT,
        name TEXT,
        dosage TEXT,
        frequency TEXT,
        start_date TEXT,
        end_date TEXT DEFAULT 'Ongoing',
        notes TEXT DEFAULT '',
        FOREIGN KEY (patient_id) REFERENCES patient_records (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        full_name TEXT,
        age INTEGER DEFAULT 35,
        gender TEXT DEFAULT 'N/A',
        email TEXT UNIQUE,
        password_hash TEXT,
        specialization TEXT,
        hospital_id TEXT,
        hospital_name TEXT,
        experience_years INTEGER DEFAULT 0,
        rating REAL DEFAULT 4.5,
        is_available INTEGER DEFAULT 1,
        is_on_call INTEGER DEFAULT 0,
        phone TEXT,
        registration_number TEXT,
        degrees TEXT DEFAULT '[]',
        surgeries_performed TEXT DEFAULT '[]',
        bio TEXT,
        latitude REAL DEFAULT 22.5726,
        longitude REAL DEFAULT 88.3639,
        created_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctor_patient_access (
        doctor_id TEXT,
        patient_id TEXT,
        granted_at TEXT,
        is_active INTEGER DEFAULT 1,
        PRIMARY KEY (doctor_id, patient_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hospitals (
        id TEXT PRIMARY KEY,
        name TEXT,
        address TEXT,
        phone TEXT,
        latitude REAL,
        longitude REAL,
        total_beds INTEGER DEFAULT 100,
        available_beds INTEGER DEFAULT 40,
        icu_beds_available INTEGER DEFAULT 10,
        liquid_oxygen_percentage REAL DEFAULT 80.0,
        oxygen_cylinders_available INTEGER DEFAULT 50,
        organs_available TEXT DEFAULT '[]'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS blood_inventory (
        hospital_id TEXT,
        blood_group TEXT,
        units_available INTEGER DEFAULT 0,
        PRIMARY KEY (hospital_id, blood_group),
        FOREIGN KEY (hospital_id) REFERENCES hospitals (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ambulances (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        number_plate TEXT UNIQUE,
        call_sign TEXT,
        type TEXT DEFAULT 'ALS',
        hospital_id TEXT,
        hospital_name TEXT,
        driver_name TEXT,
        driver_phone TEXT,
        latitude REAL,
        longitude REAL,
        status TEXT DEFAULT 'AVAILABLE',
        green_corridor_active INTEGER DEFAULT 0,
        FOREIGN KEY (hospital_id) REFERENCES hospitals (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS emergencies (
        id TEXT PRIMARY KEY,
        patient_id TEXT,
        caller_name TEXT,
        phone TEXT,
        disaster_type TEXT,
        severity TEXT DEFAULT 'CRITICAL',
        latitude REAL,
        longitude REAL,
        address TEXT,
        notes TEXT,
        status TEXT DEFAULT 'ACTIVE',
        assigned_hospital_id TEXT,
        ambulance_count INTEGER DEFAULT 1,
        created_at TEXT,
        resolved_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS emergency_ambulances (
        emergency_id TEXT,
        ambulance_id TEXT,
        status TEXT DEFAULT 'REQUESTED',
        assigned_at TEXT,
        notes TEXT,
        PRIMARY KEY (emergency_id, ambulance_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS emergency_doctors (
        emergency_id TEXT,
        doctor_id TEXT,
        status TEXT DEFAULT 'REQUESTED',
        requested_at TEXT,
        accepted_at TEXT,
        notes TEXT,
        PRIMARY KEY (emergency_id, doctor_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS triage_assessments (
        id TEXT PRIMARY KEY,
        patient_id TEXT,
        emergency_id TEXT,
        can_walk INTEGER DEFAULT 1,
        vitals_stable INTEGER DEFAULT 1,
        respiration_rate INTEGER DEFAULT 18,
        radial_pulse INTEGER DEFAULT 1,
        follows_commands INTEGER DEFAULT 1,
        consciousness_level TEXT DEFAULT 'ALERT',
        chief_complaint TEXT,
        triage_tag TEXT,
        auto_dispatched INTEGER DEFAULT 0,
        assessed_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS organ_transports (
        id TEXT PRIMARY KEY,
        organ_type TEXT,
        donor_hospital_id TEXT,
        donor_hospital_name TEXT,
        recipient_hospital_id TEXT,
        recipient_hospital_name TEXT,
        ambulance_id TEXT,
        harvested_at TEXT,
        viability_hours REAL,
        status TEXT DEFAULT 'VIABLE',
        corridor_active INTEGER DEFAULT 1,
        notes TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS officer_checkins (
        id TEXT PRIMARY KEY,
        ambulance_id TEXT,
        officer_name TEXT,
        checked_in_at TEXT,
        latitude REAL,
        longitude REAL,
        notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS traffic_signals (
        id TEXT PRIMARY KEY,
        intersection_name TEXT,
        latitude REAL,
        longitude REAL,
        current_state TEXT DEFAULT 'RED',
        green_corridor_active INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS disaster_broadcasts (
        id TEXT PRIMARY KEY,
        created_at TEXT,
        title TEXT,
        hazard_type TEXT,
        severity TEXT,
        description TEXT,
        safety_instructions TEXT,
        evacuation_route TEXT,
        is_active INTEGER DEFAULT 1
    )
    """)

    conn.commit()
    seed_initial_data(conn)
    conn.close()


def seed_initial_data(conn):
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    cursor.execute("SELECT COUNT(*) FROM hospitals")
    if cursor.fetchone()[0] == 0:
        hospitals = [
            ("HOSP-01","Apollo Trauma & Multispecialty Center","EM Bypass, Kolkata","+91-33-2320-3040",22.5200,88.3950,200,45,18,92.0,65,'["KIDNEY","CORNEA"]'),
            ("HOSP-02","City Emergency & General Hospital","Sealdah, Kolkata","+91-33-2350-7890",22.5640,88.3710,150,30,10,75.0,40,'["CORNEA"]'),
            ("HOSP-03","St. Jude Critical Care Institute","New Town, Rajarhat","+91-33-2580-2210",22.5890,88.4450,180,55,22,88.0,55,'["LIVER","KIDNEY","HEART"]'),
            ("HOSP-04","Metro Memorial Trauma Unit","Salt Lake, Kolkata","+91-33-2337-0001",22.5770,88.4120,120,22,8,65.0,30,'[]'),
            ("HOSP-05","Green Valley Children & Emergency","Howrah, WB","+91-33-2638-1234",22.5877,88.3082,100,18,6,80.0,35,'["CORNEA"]'),
        ]
        cursor.executemany("""
            INSERT INTO hospitals (id,name,address,phone,latitude,longitude,total_beds,available_beds,icu_beds_available,liquid_oxygen_percentage,oxygen_cylinders_available,organs_available)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, hospitals)

        blood_seeds = [
            ("HOSP-01",{"A+":18,"A-":4,"B+":22,"B-":3,"AB+":9,"AB-":2,"O+":25,"O-":5}),
            ("HOSP-02",{"A+":10,"A-":2,"B+":14,"B-":1,"AB+":5,"AB-":1,"O+":16,"O-":3}),
            ("HOSP-03",{"A+":20,"A-":5,"B+":28,"B-":4,"AB+":11,"AB-":3,"O+":30,"O-":7}),
            ("HOSP-04",{"A+":7,"A-":1,"B+":9,"B-":0,"AB+":3,"AB-":0,"O+":10,"O-":2}),
            ("HOSP-05",{"A+":12,"A-":2,"B+":15,"B-":2,"AB+":6,"AB-":1,"O+":18,"O-":3}),
        ]
        for hosp_id, inv in blood_seeds:
            for bg, units in inv.items():
                cursor.execute("INSERT OR IGNORE INTO blood_inventory VALUES (?,?,?)",(hosp_id,bg,units))

    cursor.execute("SELECT COUNT(*) FROM traffic_signals")
    if cursor.fetchone()[0] == 0:
        signals = [
            ("SIG-01","EM Bypass & Science City Junction",22.5410,88.3980,"RED",0),
            ("SIG-02","Park Street & AJC Bose Crossing",22.5510,88.3520,"GREEN",0),
            ("SIG-03","Salt Lake Sector V Gate",22.5760,88.4300,"RED",0),
            ("SIG-04","Ultadanga Bridge Junction",22.5840,88.3870,"GREEN",0),
            ("SIG-05","Howrah Bridge South",22.5820,88.3470,"RED",0),
            ("SIG-06","New Town Action Area I",22.5915,88.4620,"GREEN",0),
        ]
        cursor.executemany("INSERT INTO traffic_signals VALUES (?,?,?,?,?,?)",signals)

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)",
            ("USR-P001","patient@demo.com","hash_demoxxxx","PATIENT","P-101",now,now))
        cursor.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)",
            ("USR-D001","doctor@demo.com","hash_demoxxxx","DOCTOR","DOC-001",now,now))
        cursor.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)",
            ("USR-A001","ambulance@demo.com","hash_demoxxxx","AMBULANCE","AMB-101",now,now))

    cursor.execute("SELECT COUNT(*) FROM patient_records")
    if cursor.fetchone()[0] == 0:
        patients = [
            ("P-101","USR-P001","Arjun Sharma",28,"Male","1998-03-15","B+",
             '["Penicillin Allergy","NSAIDs Sensitivity"]',
             '["Type 2 Diabetes","Hypertension"]',
             '["Metformin 500mg","Amlodipine 5mg"]',
             "Appendectomy (2019), Right knee arthroscopy (2021)",
             '[{"name":"Priya Sharma","phone":"+91-98300-11234"}]',
             "MediShield Premium MED-2023-112233","1234",now),
            ("P-102","","Meera Nair",45,"Female","1981-07-22","A+",
             '["Sulfa drugs"]','["Asthma","Hypothyroidism"]',
             '["Levothyroxine 50mcg","Salbutamol Inhaler"]',
             "Thyroidectomy (2015)",
             '[{"name":"Suresh Nair","phone":"+91-94400-55678"}]',
             "","5678",now),
            ("P-103","","Bilal Ahmed",62,"Male","1964-11-10","O-",
             '[]','["Coronary Artery Disease","CKD Stage 3"]',
             '["Aspirin 75mg","Atorvastatin 40mg","Carvedilol 6.25mg"]',
             "CABG (2018), Coronary angioplasty (2020)",
             '[{"name":"Fatima Ahmed","phone":"+91-99000-77890"}]',
             "","9012",now),
        ]
        cursor.executemany("""
            INSERT INTO patient_records (id,user_id,full_name,age,gender,dob,blood_group,known_allergies,chronic_conditions,current_medications,past_surgeries,emergency_contacts,insurance_policy,access_pin,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, patients)

        meds = [
            ("MED-001","P-101","Metformin","500mg","Twice daily with meals","2023-01-15","Ongoing","Monitor blood sugar"),
            ("MED-002","P-101","Amlodipine","5mg","Once daily morning","2023-01-15","Ongoing","Check BP daily"),
            ("MED-003","P-102","Levothyroxine","50mcg","Once daily empty stomach","2022-06-01","Ongoing","30 min before breakfast"),
            ("MED-004","P-103","Aspirin","75mg","Once daily after breakfast","2019-03-01","Ongoing","Do not skip"),
        ]
        cursor.executemany("""
            INSERT INTO patient_medications (id,patient_id,name,dosage,frequency,start_date,end_date,notes)
            VALUES (?,?,?,?,?,?,?,?)
        """, meds)

    cursor.execute("SELECT COUNT(*) FROM doctors")
    if cursor.fetchone()[0] == 0:
        doctors = [
            ("DOC-001","USR-D001","Dr. Ananya Dasgupta",42,"Female","ananya@demo.com","hash_demoxxxx",
             "Trauma Surgery","HOSP-01","Apollo Trauma & Multispecialty Center",14,4.9,1,1,
             "+91-98200-10001","MCI-2010-TRU-88423",
             '["MBBS (AIIMS Delhi 2004)","MS Surgery (PGIMER 2008)","MCh Trauma (AIIMS 2010)"]',
             '["Damage Control Surgery x 200+","Polytrauma Management x 150+","Exploratory Laparotomy x 120+"]',
             "Trauma surgery chief with ATLS certification. Expert in polytrauma and penetrating injuries.",
             22.5200,88.3950,now),
            ("DOC-002","","Dr. Rohan Mehta",47,"Male","rohan@resqnet.in","hash_pass_2",
             "Cardiology","HOSP-03","St. Jude Critical Care Institute",11,4.8,1,1,
             "+91-98200-10002","MCI-2012-CAR-65201",
             '["MBBS (KEM Mumbai 2001)","MD Medicine (PGIMER 2005)","DM Cardiology (AIIMS 2009)"]',
             '["Primary PTCA x 500+","CABG x 80+","Pacemaker Implant x 120+"]',
             "Interventional cardiologist. Expert in primary PTCA and cardiac arrest resuscitation.",
             22.5890,88.4450,now),
            ("DOC-003","","Dr. Priya Subramaniam",38,"Female","priya@resqnet.in","hash_pass_3",
             "Neurology","HOSP-01","Apollo Trauma & Multispecialty Center",9,4.7,1,0,
             "+91-98200-10003","MCI-2014-NEU-74110",
             '["MBBS (CMC Vellore 2007)","MD Neurology (AIIMS 2011)","Fellowship Stroke (Johns Hopkins 2013)"]',
             '["Mechanical Thrombectomy x 60+","Thrombolysis x 150+","Lumbar Puncture x 300+"]',
             "Stroke neurologist specializing in time-critical thrombolysis and head trauma.",
             22.5200,88.3950,now),
            ("DOC-004","","Dr. Karan Nair",35,"Male","karan@resqnet.in","hash_pass_4",
             "General Emergency Medicine","HOSP-02","City Emergency & General Hospital",7,4.6,1,1,
             "+91-98200-10004","MCI-2016-EM-90022",
             '["MBBS (Grant Medical Mumbai 2010)","DNB Emergency Medicine (2015)","FCCS Certified"]',
             '["Rapid Sequence Intubation x 200+","Central Line Placement x 100+"]',
             "Board-certified EM physician. Expert in rapid stabilization.",
             22.5640,88.3710,now),
            ("DOC-005","","Dr. Fatima Shaikh",40,"Female","fatima@resqnet.in","hash_pass_5",
             "Pediatric Emergency","HOSP-05","Green Valley Children & Emergency",8,4.8,1,0,
             "+91-98200-10005","MCI-2013-PED-58310",
             '["MBBS (JJ Hospital Mumbai 2006)","MD Pediatrics (AIIMS 2010)","Fellowship Pediatric EM (2013)"]',
             '["Neonatal Intubation x 80+","Pediatric Trauma x 200+"]',
             "Pediatric emergency specialist. Expert in neonatal and childhood trauma.",
             22.5877,88.3082,now),
            ("DOC-006","","Dr. Vikram Bose",52,"Male","vikram@resqnet.in","hash_pass_6",
             "Trauma Surgery","HOSP-03","St. Jude Critical Care Institute",16,4.9,0,0,
             "+91-98200-10006","MCI-2008-TRU-41099",
             '["MBBS (Calcutta Medical College 1998)","MS Surgery (PGI 2002)","MCh Trauma (2006)"]',
             '["Damage Control x 300+","Mass Casualty Triage x 50 events"]',
             "Senior trauma surgeon. Damage control surgery and mass casualty triage.",
             22.5890,88.4450,now),
            ("DOC-007","","Dr. Meena Krishnan",49,"Female","meena@resqnet.in","hash_pass_7",
             "Transplant Surgery","HOSP-01","Apollo Trauma & Multispecialty Center",18,5.0,1,1,
             "+91-98200-10007","MCI-2006-TXP-31245",
             '["MBBS (JIPMER 1997)","MS Surgery (AIIMS 2001)","MCh Transplant (KEM 2004)","Fellowship USA 2006"]',
             '["Kidney Transplant x 300+","Liver Transplant x 80+","Heart Transplant x 15+"]',
             "Lead transplant surgeon. Oversees all organ corridor protocols.",
             22.5200,88.3950,now),
        ]
        cursor.executemany("""
            INSERT INTO doctors (id,user_id,full_name,age,gender,email,password_hash,specialization,hospital_id,hospital_name,experience_years,rating,is_available,is_on_call,phone,registration_number,degrees,surgeries_performed,bio,latitude,longitude,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, doctors)

    cursor.execute("SELECT COUNT(*) FROM ambulances")
    if cursor.fetchone()[0] == 0:
        ambulances = [
            ("AMB-101","USR-A001","WB-01-AB-1234","Alpha-1","ALS","HOSP-01","Apollo Trauma Center","Ranjit Das","+91-98711-00101",22.5350,88.3800,"AVAILABLE",0),
            ("AMB-102","","WB-01-CD-5678","Trauma-2","ALS","HOSP-02","City Emergency Hospital","Suresh Kumar","+91-98711-00202",22.5510,88.3620,"AVAILABLE",0),
            ("AMB-103","","WB-01-EF-9012","Cardiac-3","ICU_MOBILE","HOSP-03","St. Jude Critical Care","Amit Roy","+91-98711-00303",22.5750,88.4200,"AVAILABLE",0),
            ("AMB-104","","WB-02-GH-3456","BLS-4","BLS","HOSP-04","Metro Memorial","Pradeep Singh","+91-98711-00404",22.5820,88.4050,"AVAILABLE",0),
            ("AMB-105","","WB-02-IJ-7890","Rescue-5","ALS","HOSP-05","Green Valley Children","Debashis Ghosh","+91-98711-00505",22.5690,88.3120,"AVAILABLE",0),
        ]
        cursor.executemany("""
            INSERT INTO ambulances (id,user_id,number_plate,call_sign,type,hospital_id,hospital_name,driver_name,driver_phone,latitude,longitude,status,green_corridor_active)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, ambulances)

    cursor.execute("SELECT COUNT(*) FROM disaster_broadcasts")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""INSERT INTO disaster_broadcasts VALUES (?,?,?,?,?,?,?,?,1)""",
            ("DIS-001",now,"Monsoon Flash Flood Advisory","FLOOD","HIGH",
             "Heavy rains forecast. Flood warnings for South Kolkata.",
             "Move to higher ground. Avoid waterlogged roads. Call 112.",
             "EM Bypass to Salt Lake Elevated to Airport Road"))

    conn.commit()


if __name__ == "__main__":
    init_db()
    print(f"ResQNet 2.0 database initialized at {DB_PATH}")
