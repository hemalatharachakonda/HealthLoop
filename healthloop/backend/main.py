"""
HealthLoop backend - FastAPI
Run with: uvicorn main:app --reload --port 8000
Then open frontend/index.html in a browser (or serve it - see README).

Database: uses SQLAlchemy, so it works with SQLite (default, zero setup),
PostgreSQL, or MySQL - just set DATABASE_URL in backend/.env. See database.py.
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from pathlib import Path
import json
import io
import requests
import random
from datetime import datetime, timedelta

from database import init_db, get_db, User, Report, Reminder, MentalHealthSession, PasswordResetOTP
from ocr import extract_text_from_file
from auth import hash_password, verify_password
from pdf_service import build_diet_plan_pdf
from groq_client import (
    analyze_report,
    symptom_triage_question,
    mental_health_reply,
)
from hospital_finder import find_hospitals
from reminder_scheduler import start_scheduler
from email_service import send_parent_notification_email, send_otp_email

app = FastAPI(title="HealthLoop API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # fine for a hackathon demo; restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
start_scheduler()

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# ---------- Auth: signup / login (email + password) ----------
# Note: hackathon scope - returns user_id directly instead of a full JWT session token.
# Good enough for a demo; for a real deployment, swap this for proper session/JWT tokens.

class SignupIn(BaseModel):
    name: str
    email: str
    password: str
    phone: str | None = None
    parent_phone: str | None = None
    parent_email: str | None = None
    age: int | None = None
    language: str = "English"


@app.post("/api/auth/signup")
def signup(payload: SignupIn, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(400, "An account with this email already exists.")

    db_user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        phone=payload.phone,
        parent_phone=payload.parent_phone,
        parent_email=payload.parent_email,
        age=payload.age,
        language=payload.language,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"user_id": db_user.id, "name": db_user.name, "language": db_user.language}


class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    return {"user_id": user.id, "name": user.name, "language": user.language}


class ForgotPasswordIn(BaseModel):
    email: str


@app.post("/api/auth/forgot-password")
def forgot_password(payload: ForgotPasswordIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    # Always return the same success-shaped response whether or not the email
    # exists, so this endpoint can't be used to check which emails are registered.
    if not user:
        return {"message": "If an account exists with that email, a code has been sent."}

    otp_code = f"{random.randint(0, 999999):06d}"
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    db.add(PasswordResetOTP(email=payload.email, otp_code=otp_code, expires_at=expires_at))
    db.commit()

    send_otp_email(to_email=payload.email, otp_code=otp_code, language=user.language or "English")
    return {"message": "If an account exists with that email, a code has been sent."}


class ResetPasswordIn(BaseModel):
    email: str
    otp_code: str
    new_password: str


@app.post("/api/auth/reset-password")
def reset_password(payload: ResetPasswordIn, db: Session = Depends(get_db)):
    if len(payload.new_password) < 6:
        raise HTTPException(400, "Password should be at least 6 characters.")

    otp_entry = (
        db.query(PasswordResetOTP)
        .filter(PasswordResetOTP.email == payload.email)
        .filter(PasswordResetOTP.otp_code == payload.otp_code)
        .filter(PasswordResetOTP.used == False)  # noqa: E712
        .order_by(PasswordResetOTP.created_at.desc())
        .first()
    )

    if not otp_entry:
        raise HTTPException(400, "Invalid or already-used code.")
    if otp_entry.expires_at < datetime.utcnow():
        raise HTTPException(400, "This code has expired. Please request a new one.")

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(404, "User not found.")

    user.password_hash = hash_password(payload.new_password)
    otp_entry.used = True
    db.commit()

    return {"message": "Password reset successfully. You can now log in with your new password."}


# ---------- View own profile + data (used by a "My Data" screen) ----------

@app.get("/api/users/{user_id}/full-data")
def get_user_full_data(user_id: int, db: Session = Depends(get_db)):
    """Returns the user's profile plus their reports and reminders - lets them see
    everything stored about them in one place (transparency, and useful for a demo)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    reports = db.query(Report).filter(Report.user_id == user_id).order_by(Report.created_at.desc()).all()
    reminders = db.query(Reminder).filter(Reminder.user_id == user_id).order_by(Reminder.created_at.desc()).all()

    return {
        "profile": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "parent_phone": user.parent_phone,
            "parent_email": user.parent_email,
            "age": user.age,
            "language": user.language,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "reports": [
            {
                "id": r.id,
                "primary_finding": r.primary_finding,
                "other_findings": r.other_findings,
                "language": r.language,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ],
        "reminders": [
            {
                "id": r.id,
                "medicine_name": r.medicine_name,
                "dosage": r.dosage,
                "frequency": r.frequency,
                "taken": r.taken,
            }
            for r in reminders
        ],
    }


@app.get("/api/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return {
        "id": user.id, "name": user.name, "email": user.email,
        "phone": user.phone, "parent_phone": user.parent_phone, "parent_email": user.parent_email,
        "age": user.age, "language": user.language,
    }


# ---------- Module 1: Report upload + analysis ----------

@app.post("/api/reports/analyze")
async def analyze_report_endpoint(
    files: list[UploadFile] = File(...),
    language: str = Form("English"),
    user_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """
    Accepts one or more files (multiple photos of the same report, or a single PDF).
    Text from all files is combined before analysis, since a report can span multiple
    pages/photos - Groq sees the whole thing at once rather than one page in isolation.
    """
    combined_text_parts = []
    failed_files = []

    for f in files:
        file_bytes = await f.read()
        try:
            extracted = extract_text_from_file(file_bytes, f.content_type)
        except Exception:
            extracted = ""
        if extracted and len(extracted.strip()) >= 5:
            combined_text_parts.append(extracted)
        else:
            failed_files.append(f.filename or "unnamed file")

    raw_text = "\n\n---\n\n".join(combined_text_parts)

    if not raw_text or len(raw_text.strip()) < 10:
        raise HTTPException(
            400,
            "Could not read enough text from the uploaded file(s). "
            "For photos, please retake with better lighting. "
            "For PDFs, make sure it's a text-based PDF, not a scanned image with no text layer.",
        )

    # Safety cap: some PDFs (multi-page directories, long forms, etc.) extract far more text
    # than a normal 1-2 page lab report ever would. Without a cap, a large enough file makes
    # the request body itself too big for Groq's API to accept (a 413 error, distinct from
    # the 429 rate-limit case handled in groq_client.py) - this truncates before that point
    # is ever reached, rather than failing the whole upload.
    # (Lowered from 12000 - that was still triggering 413s on larger multi-page PDFs.)
    MAX_REPORT_CHARS = 6000
    was_truncated = len(raw_text) > MAX_REPORT_CHARS
    if was_truncated:
        raw_text = raw_text[:MAX_REPORT_CHARS]

    try:
        analysis = analyze_report(raw_text, language=language)
    except Exception as e:
        # If Groq (or any part of the analysis call) fails, return a clean JSON error
        # instead of letting an unhandled exception crash the request - an unhandled
        # crash skips CORS headers entirely, which browsers misreport as a CORS error.
        raise HTTPException(502, f"Report analysis failed: {e}")

    medicines = analysis.get("medicines", [])

    db_report = Report(
        user_id=user_id,
        raw_text=raw_text,
        primary_finding=json.dumps(analysis.get("primary_finding", {})),
        other_findings=json.dumps(analysis.get("other_findings", [])),
        normal_findings=json.dumps(analysis.get("normal_findings", [])),
        diet_tips=json.dumps(analysis.get("primary_finding", {}).get("diet_tips", [])),
        diet_plan=json.dumps(analysis.get("diet_plan", {})),
        language=language,
    )
    db.add(db_report)

    # auto-create reminders from any detected medicines
    for med in medicines:
        db.add(Reminder(
            user_id=user_id,
            medicine_name=med.get("medicine_name", ""),
            dosage=med.get("dosage", ""),
            frequency=med.get("frequency", ""),
        ))

    db.commit()
    db.refresh(db_report)

    return {
        "report_id": db_report.id,
        "analysis": analysis,
        "medicines_detected": medicines,
        "raw_text_preview": raw_text[:300],
        "files_processed": len(combined_text_parts),
        "files_failed": failed_files,
        "was_truncated": was_truncated,
    }


@app.get("/api/reports")
def list_reports(user_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Report)
    if user_id:
        query = query.filter(Report.user_id == user_id)
    reports = query.order_by(Report.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "primary_finding": r.primary_finding,
            "other_findings": r.other_findings,
            "normal_findings": r.normal_findings,
            "diet_tips": r.diet_tips,
            "diet_plan": r.diet_plan,
            "language": r.language,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]


@app.get("/api/reports/{report_id}/diet-plan-pdf")
def download_diet_plan_pdf(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(404, "Report not found")

    diet_plan = json.loads(report.diet_plan or "{}")
    primary = json.loads(report.primary_finding or "{}")
    other_findings = json.loads(report.other_findings or "[]")
    normal_findings = json.loads(report.normal_findings or "[]")

    if not diet_plan and not other_findings and not normal_findings and not primary:
        raise HTTPException(400, "No report data available to build a PDF from.")

    patient_name = "Patient"
    if report.user_id:
        user = db.query(User).filter(User.id == report.user_id).first()
        if user:
            patient_name = user.name

    pdf_bytes = build_diet_plan_pdf(
        patient_name=patient_name,
        primary_finding=primary,
        other_findings=other_findings,
        normal_findings=normal_findings,
        diet_plan=diet_plan,
        language=report.language or "English",
    )
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=healthloop_diet_plan_{report_id}.pdf"},
    )


# ---------- Module 2: Reminders ----------

@app.get("/api/reminders")
def list_reminders(user_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Reminder)
    if user_id:
        query = query.filter(Reminder.user_id == user_id)
    reminders = query.order_by(Reminder.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "medicine_name": r.medicine_name,
            "dosage": r.dosage,
            "frequency": r.frequency,
            "reminder_time": r.reminder_time,
            "taken": r.taken,
        }
        for r in reminders
    ]


@app.post("/api/reminders/{reminder_id}/taken")
def mark_taken(reminder_id: int, db: Session = Depends(get_db)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(404, "Reminder not found")
    reminder.taken = True
    db.commit()
    return {"status": "ok"}


class ReminderIn(BaseModel):
    user_id: int | None = None
    medicine_name: str = ""    # optional - user can skip straight to just setting a time
    dosage: str = ""
    frequency: str = ""
    reminder_time: str | None = None   # "HH:MM" 24-hour format, e.g. "08:00"


@app.post("/api/reminders")
def create_reminder(reminder: ReminderIn, db: Session = Depends(get_db)):
    db_reminder = Reminder(
        user_id=reminder.user_id,
        medicine_name=reminder.medicine_name or None,
        dosage=reminder.dosage or None,
        frequency=reminder.frequency or None,
        reminder_time=reminder.reminder_time,
    )
    db.add(db_reminder)
    db.commit()
    db.refresh(db_reminder)
    return {"reminder_id": db_reminder.id}


# ---------- Module 5: Symptom triage (adaptive interview) ----------

class TriageIn(BaseModel):
    conversation_history: list  # [{"role": "user"/"assistant", "content": "..."}]
    language: str = "English"


@app.post("/api/triage/next")
def triage_next(payload: TriageIn):
    try:
        result = symptom_triage_question(payload.conversation_history, language=payload.language)
    except Exception as e:
        raise HTTPException(502, f"Triage assistant failed: {e}")
    return result


class HospitalSearchIn(BaseModel):
    lat: float
    lon: float
    is_emergency: bool = False
    radius_m: int = 5000
    specialty: str | None = None


@app.post("/api/hospitals/nearby")
def hospitals_nearby(payload: HospitalSearchIn):
    """
    Called after triage/next returns done=true. Pass is_emergency based on whether
    recommended_specialty came back as "Emergency / ER" (see groq_client.symptom_triage_question).
    `specialty` is Groq's recommended_specialty - used to prioritize hospitals confirmed to
    offer that specialty (currently only for Vijayawada, see curated_hospitals.py).
    """
    try:
        results = find_hospitals(
            lat=payload.lat,
            lon=payload.lon,
            is_emergency=payload.is_emergency,
            radius_m=payload.radius_m,
            specialty=payload.specialty,
        )
    except requests.exceptions.RequestException:
        raise HTTPException(503, "Could not reach hospital lookup service. Please try again.")
    return {"hospitals": results, "mode": "emergency" if payload.is_emergency else "routine"}


# ---------- Module 3: Mental health check-in ----------

class MentalHealthIn(BaseModel):
    conversation_history: list
    language: str = "English"
    user_id: int | None = None


@app.post("/api/mental-health/reply")
def mental_health_endpoint(payload: MentalHealthIn, db: Session = Depends(get_db)):
    try:
        result = mental_health_reply(payload.conversation_history, language=payload.language)
    except Exception as e:
        raise HTTPException(502, f"Mental health assistant failed: {e}")

    last_msg = payload.conversation_history[-1]["content"] if payload.conversation_history else ""
    db.add(MentalHealthSession(user_id=payload.user_id, message=last_msg, role="user", risk_flag=False))
    db.add(MentalHealthSession(
        user_id=payload.user_id,
        message=result["reply"],
        role="assistant",
        risk_flag=bool(result.get("risk_flag", False)),
    ))
    db.commit()

    return result


class NotifyParentIn(BaseModel):
    user_id: int


@app.post("/api/mental-health/notify-parent")
def notify_parent(payload: NotifyParentIn, db: Session = Depends(get_db)):
    """
    Called only after the student explicitly consents in the crisis-alert UI
    (see mental-health.html's "Yes, please notify someone" button) - never
    triggered automatically or without the student seeing it happen.
    """
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    if not user.parent_email:
        return {"sent": False, "reason": "No parent/guardian email is on file for this account."}

    sent = send_parent_notification_email(
        to_email=user.parent_email,
        student_name=user.name,
        language=user.language or "English",
    )
    return {"sent": sent, "reason": None if sent else "Email could not be sent - check server logs."}


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
