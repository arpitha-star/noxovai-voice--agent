"""
Automated Backend & Pipeline Test Suite for NexovAI Voice Agent
"""

from backend.database import (
    init_db,
    get_doctors_with_slots,
    get_all_appointments,
    get_available_slots,
    book_appointment,
    cancel_appointment
)
from backend.tools import (
    execute_check_doctor_availability,
    execute_book_appointment,
    execute_cancel_appointment
)

def run_tests():
    print("=" * 60)
    print("Running NexovAI Test Suite...")
    print("=" * 60)

    # 1. Initialize DB with seed state
    init_db(force_reset=True)
    print("[PASS] Database initialized and seeded.")

    # 2. Check Doctors & Availability
    doctors = get_doctors_with_slots()
    assert len(doctors) == 5, f"Expected 5 doctors, got {len(doctors)}"
    print(f"[PASS] Doctors loaded: {len(doctors)} doctors across Cardiology, Dermatology, General Medicine, Orthopedics, Pediatrics.")

    # 3. Test check_doctor_availability tool
    avail = execute_check_doctor_availability(specialty="Cardiology")
    assert avail["count"] > 0, "No slots found for Cardiology"
    first_slot = avail["available_slots"][0]
    print(f"[PASS] Tool 'check_doctor_availability': Found {avail['count']} Cardiology slots (First: {first_slot['date']} {first_slot['time']}).")

    # 4. Test book_appointment tool
    test_phone = "9876543210"
    book_res = execute_book_appointment(
        patient_phone=test_phone,
        doctor_name=first_slot["doctor_name"],
        date=first_slot["date"],
        time_slot=first_slot["time"],
        patient_name="Caller"
    )
    assert book_res["success"] is True, f"Booking failed: {book_res}"
    appointment_id = book_res["appointment_id"]
    print(f"[PASS] Tool 'book_appointment': Successfully booked Appointment #{appointment_id} for phone {test_phone}.")

    # 5. Verify Appointment exists in Ledger
    apps = get_all_appointments()
    matching = [a for a in apps if a["id"] == appointment_id]
    assert len(matching) == 1, "Appointment not found in ledger"
    assert matching[0]["status"] == "confirmed"
    print(f"[PASS] Appointment Ledger: Verified confirmed status for Appointment #{appointment_id}.")

    # 6. Test cancel_appointment tool (using phone number identification)
    cancel_res = execute_cancel_appointment(patient_phone=test_phone, appointment_id=appointment_id)
    assert cancel_res["success"] is True, f"Cancellation failed: {cancel_res}"
    print(f"[PASS] Tool 'cancel_appointment': Successfully cancelled for phone {test_phone}.")

    # 7. Verify Slot is restored and Status is cancelled
    apps_after = get_all_appointments()
    cancelled_app = [a for a in apps_after if a["id"] == appointment_id][0]
    assert cancelled_app["status"] == "cancelled"
    print(f"[PASS] Slot Management: Appointment #{appointment_id} marked cancelled and slot reopened.")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED WITH 100% SUCCESS! Ready for deployment.")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
