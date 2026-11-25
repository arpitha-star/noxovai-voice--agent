"""
NexovAI Voice AI Doctor Appointment Assistant
Database Layer (SQLite)
Manages Doctors, Slots, and Appointments.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "appointments.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force_reset: bool = False):
    """Initialize database tables and seed mock data if not exists."""
    if force_reset and os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception as e:
            print(f"Error removing db for reset: {e}")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        specialty TEXT NOT NULL,
        department TEXT NOT NULL,
        rating REAL DEFAULT 4.9,
        avatar_initials TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'available',
        FOREIGN KEY (doctor_id) REFERENCES doctors (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id INTEGER NOT NULL,
        doctor_name TEXT NOT NULL,
        specialty TEXT NOT NULL,
        patient_phone TEXT NOT NULL,
        patient_name TEXT DEFAULT 'Caller',
        date TEXT NOT NULL,
        time_slot TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'confirmed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (doctor_id) REFERENCES doctors (id)
    );
    """)

    # Seed initial data if doctors table is empty
    cursor.execute("SELECT COUNT(*) as count FROM doctors")
    if cursor.fetchone()["count"] == 0:
        _seed_mock_data(cursor)

    conn.commit()
    conn.close()


def _seed_mock_data(cursor):
    """Seed realistic mock doctors and upcoming availability."""
    doctors = [
        ("Dr. Sarah Chen", "Cardiology", "Heart & Vascular Center", 4.9, "SC"),
        ("Dr. Rajesh Patel", "Dermatology", "Skin & Aesthetics Clinic", 4.8, "RP"),
        ("Dr. Elena Rostova", "General Medicine", "Primary Care Health", 4.9, "ER"),
        ("Dr. Marcus Johnson", "Orthopedics", "Bone & Joint Institute", 4.7, "MJ"),
        ("Dr. Aisha Sharma", "Pediatrics", "Children & Adolescent Care", 5.0, "AS"),
    ]

    cursor.executemany(
        "INSERT INTO doctors (name, specialty, department, rating, avatar_initials) VALUES (?, ?, ?, ?, ?)",
        doctors
    )

    # Fetch doctor IDs
    cursor.execute("SELECT id, name, specialty FROM doctors")
    doctor_rows = cursor.fetchall()

    today = datetime.now()
    dates = [
        today.strftime("%Y-%m-%d"),
        (today + timedelta(days=1)).strftime("%Y-%m-%d"),
        (today + timedelta(days=2)).strftime("%Y-%m-%d"),
        (today + timedelta(days=3)).strftime("%Y-%m-%d"),
    ]

    time_slots = ["09:30 AM", "11:00 AM", "02:00 PM", "03:30 PM", "05:00 PM"]

    slots_to_insert = []
    for doc in doctor_rows:
        doc_id = doc["id"]
        for d in dates:
            for t in time_slots:
                # Add slot
                slots_to_insert.append((doc_id, d, t, 'available'))

    cursor.executemany(
        "INSERT INTO slots (doctor_id, date, time, status) VALUES (?, ?, ?, ?)",
        slots_to_insert
    )

    # Add 2 sample pre-booked appointments so caller can test cancellation right away
    # e.g., phone: "9876543210" and "5551234567"
    sample_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    # Book Dr. Sarah Chen at 11:00 AM for 9876543210
    cursor.execute(
        "UPDATE slots SET status = 'booked' WHERE doctor_id = 1 AND date = ? AND time = '11:00 AM'",
        (sample_date,)
    )
    cursor.execute("""
        INSERT INTO appointments (doctor_id, doctor_name, specialty, patient_phone, patient_name, date, time_slot, status)
        VALUES (1, 'Dr. Sarah Chen', 'Cardiology', '9876543210', 'Alex Taylor', ?, '11:00 AM', 'confirmed')
    """, (sample_date,))

    # Book Dr. Rajesh Patel at 03:30 PM for 5551234567
    cursor.execute(
        "UPDATE slots SET status = 'booked' WHERE doctor_id = 2 AND date = ? AND time = '03:30 PM'",
        (sample_date,)
    )
    cursor.execute("""
        INSERT INTO appointments (doctor_id, doctor_name, specialty, patient_phone, patient_name, date, time_slot, status)
        VALUES (2, 'Dr. Rajesh Patel', 'Dermatology', '5551234567', 'Jordan Lee', ?, '03:30 PM', 'confirmed')
    """, (sample_date,))


def get_doctors_with_slots() -> List[Dict[str, Any]]:
    """Retrieve all doctors with their available upcoming slots."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM doctors ORDER BY name ASC")
    doctors = [dict(row) for row in cursor.fetchall()]

    for doc in doctors:
        cursor.execute(
            "SELECT id, date, time, status FROM slots WHERE doctor_id = ? AND status = 'available' ORDER BY date ASC, time ASC",
            (doc["id"],)
        )
        doc["available_slots"] = [dict(s) for s in cursor.fetchall()]

    conn.close()
    return doctors


def get_available_slots(doctor_name: Optional[str] = None, specialty: Optional[str] = None, date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Query available slots matching criteria for the voice pipeline."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    SELECT s.id as slot_id, s.date, s.time, d.id as doctor_id, d.name as doctor_name, d.specialty
    FROM slots s
    JOIN doctors d ON s.doctor_id = d.id
    WHERE s.status = 'available'
    """
    params = []

    if doctor_name:
        query += " AND LOWER(d.name) LIKE LOWER(?)"
        params.append(f"%{doctor_name}%")

    if specialty:
        query += " AND LOWER(d.specialty) LIKE LOWER(?)"
        params.append(f"%{specialty}%")

    if date:
        # Handle simple relative dates if passed
        query += " AND s.date = ?"
        params.append(date)

    query += " ORDER BY s.date ASC, s.time ASC LIMIT 10"

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def book_appointment(patient_phone: str, doctor_name: str, date: str, time_slot: str, patient_name: str = "Caller") -> Dict[str, Any]:
    """Book an appointment for a caller. Caller is identified by phone number."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clean phone number (strip whitespace and common separators)
    clean_phone = "".join(filter(lambda c: c.isdigit() or c == "+", patient_phone.strip()))

    # Find doctor
    cursor.execute("SELECT id, name, specialty FROM doctors WHERE LOWER(name) LIKE LOWER(?) LIMIT 1", (f"%{doctor_name}%",))
    doc = cursor.fetchone()
    if not doc:
        conn.close()
        return {"success": False, "error": f"Doctor '{doctor_name}' not found."}

    doc_id = doc["id"]
    doc_real_name = doc["name"]
    doc_specialty = doc["specialty"]

    # Check slot
    cursor.execute(
        "SELECT id, status FROM slots WHERE doctor_id = ? AND date = ? AND LOWER(time) = LOWER(?) LIMIT 1",
        (doc_id, date, time_slot.strip())
    )
    slot = cursor.fetchone()

    if not slot:
        # Try matching time without strict format e.g. "9:30" vs "09:30 AM"
        cursor.execute(
            "SELECT id, time, status FROM slots WHERE doctor_id = ? AND date = ? AND (time LIKE ? OR time LIKE ?)",
            (doc_id, date, f"%{time_slot}%", f"%{time_slot.replace(' ', '')}%")
        )
        slot = cursor.fetchone()

    if not slot:
        conn.close()
        return {"success": False, "error": f"Slot {time_slot} on {date} for {doc_real_name} is not available."}

    actual_time = slot["time"] if "time" in slot.keys() else time_slot

    # Mark slot as booked
    cursor.execute("UPDATE slots SET status = 'booked' WHERE id = ?", (slot["id"],))

    # Check if an existing confirmed appointment already exists for this slot (e.g. from repeated testing)
    cursor.execute(
        "SELECT id FROM appointments WHERE doctor_id = ? AND date = ? AND time_slot = ? AND status = 'confirmed'",
        (doc_id, date, actual_time)
    )
    existing_app = cursor.fetchone()
    if existing_app:
        cursor.execute(
            "UPDATE appointments SET patient_phone = ?, patient_name = ?, status = 'confirmed' WHERE id = ?",
            (clean_phone, patient_name, existing_app["id"])
        )
        appointment_id = existing_app["id"]
    else:
        # Insert new confirmed appointment
        cursor.execute("""
            INSERT INTO appointments (doctor_id, doctor_name, specialty, patient_phone, patient_name, date, time_slot, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed')
        """, (doc_id, doc_real_name, doc_specialty, clean_phone, patient_name, date, actual_time))
        appointment_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return {
        "success": True,
        "appointment_id": appointment_id,
        "doctor_name": doc_real_name,
        "specialty": doc_specialty,
        "patient_phone": clean_phone,
        "patient_name": patient_name,
        "date": date,
        "time_slot": actual_time,
        "status": "confirmed"
    }


def cancel_appointment(patient_phone: str, appointment_id: Optional[int] = None) -> Dict[str, Any]:
    """Cancel an appointment using the phone number spoken by caller."""
    conn = get_db_connection()
    cursor = conn.cursor()

    import re
    digits = re.sub(r'\D', '', patient_phone)
    phone_key = digits[-10:] if len(digits) >= 10 else digits

    if appointment_id:
        cursor.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
    else:
        cursor.execute(
            "SELECT * FROM appointments WHERE (patient_phone LIKE ? OR patient_phone = ?) AND status = 'confirmed' ORDER BY id DESC LIMIT 1",
            (f"%{phone_key}%", phone_key)
        )
    appt = cursor.fetchone()

    if not appt:
        # If no strictly 'confirmed' appointment found, check any appointment for this phone
        cursor.execute(
            "SELECT * FROM appointments WHERE patient_phone LIKE ? ORDER BY id DESC LIMIT 1",
            (f"%{phone_key}%",)
        )
        appt = cursor.fetchone()

    if not appt:
        conn.close()
        return {"success": False, "error": f"No active appointment found for phone number {phone_key}."}

    # Cancel appointment
    cursor.execute("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (appt["id"],))

    # Free the slot
    cursor.execute(
        "UPDATE slots SET status = 'available' WHERE doctor_id = ? AND date = ? AND time = ?",
        (appt["doctor_id"], appt["date"], appt["time_slot"])
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "appointment_id": appt["id"],
        "cancelled_appointment_id": appt["id"],
        "doctor_name": appt["doctor_name"],
        "date": appt["date"],
        "time_slot": appt["time_slot"],
        "patient_phone": appt["patient_phone"],
        "message": f"Appointment with {appt['doctor_name']} on {appt['date']} at {appt['time_slot']} has been successfully cancelled."
    }


def get_all_appointments() -> List[Dict[str, Any]]:
    """Get all appointments for the dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointments ORDER BY id DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows
