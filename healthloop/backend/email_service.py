"""
Sends reminder emails using Gmail SMTP - completely free, no per-message cost,
unlike SMS providers. Requires a Gmail "app password" (not your real Gmail
password) - set up at https://myaccount.google.com/apppasswords
(needs 2-factor authentication enabled on the Gmail account first).

Set these in backend/.env:
  EMAIL_ADDRESS=youraddress@gmail.com
  EMAIL_APP_PASSWORD=your_16_char_app_password
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_reminder_email(to_email: str, patient_name: str, medicine_name: str, dosage: str, frequency: str) -> bool:
    """Returns True if sent successfully, False otherwise (never raises - a failed
    reminder email should not crash the scheduler loop that calls this)."""
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        print("[email_service] EMAIL_ADDRESS / EMAIL_APP_PASSWORD not configured - skipping email.")
        return False

    subject = f"Medicine Reminder - {medicine_name or 'Time to take your medicine'}"
    body_lines = [f"Hi {patient_name},", "", "This is your HealthLoop medicine reminder."]
    if medicine_name:
        body_lines.append(f"Medicine: {medicine_name}")
    if dosage:
        body_lines.append(f"Dosage: {dosage}")
    if frequency:
        body_lines.append(f"Frequency: {frequency}")
    body_lines += ["", "Stay healthy!", "- HealthLoop"]
    body = "\n".join(body_lines)

    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[email_service] Failed to send reminder email to {to_email}: {e}")
        return False


def send_parent_notification_email(to_email: str, student_name: str, language: str = "English") -> bool:
    """
    Sent only when a student in a mental-health check-in shows signs of real risk
    AND explicitly consents to a parent/guardian being notified - this is never
    triggered silently or without the student's knowledge (see mental-health.html's
    consent flow). Deliberately calm and non-alarmist in tone, and does not repeat
    what the student said - it invites the parent to reach out and talk, not
    frighten them with detail we can't respond to.
    """
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        print("[email_service] EMAIL_ADDRESS / EMAIL_APP_PASSWORD not configured - skipping parent notification email.")
        return False

    subject = f"A gentle note about {student_name} from HealthLoop"
    body = (
        f"Hello,\n\n"
        f"This is a message from HealthLoop, a wellbeing check-in app that {student_name} has been using.\n\n"
        f"During a recent check-in, {student_name} shared something that suggested they could use some extra "
        f"support right now, and they asked us to let you know.\n\n"
        f"We'd gently encourage you to check in with them soon - a simple, caring conversation can mean a lot. "
        f"If it feels urgent, please don't hesitate to reach out to a counselor or a mental health professional as well.\n\n"
        f"This message was sent only with {student_name}'s knowledge and consent.\n\n"
        f"Warmly,\nHealthLoop"
    )

    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[email_service] Failed to send parent notification email to {to_email}: {e}")
        return False
