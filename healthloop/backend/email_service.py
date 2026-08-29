"""
Sends reminder and parent-notification emails.

Two delivery paths, tried in this order:

1. Resend (HTTP API, port 443) - used automatically whenever RESEND_API_KEY is set.
   This is the one that actually works when deployed on Render's free tier: Render
   blocks outbound SMTP connections (ports 587/465/25) as a standard anti-abuse
   measure, which is why Gmail SMTP below fails there with "Network is unreachable" -
   that error is Render's firewall, not a credentials or code problem. Resend sends
   over plain HTTPS instead, which isn't blocked.
   Get a free key at https://resend.com (no card required). IMPORTANT limitation on
   Resend's free/unverified tier: without verifying your own domain, you can only
   send FROM their shared address (onboarding@resend.dev) TO the email address you
   signed up to Resend with - fine for a hackathon demo where you're emailing
   yourself as the test patient, but it will silently fail for other recipients
   until you verify a domain in the Resend dashboard.
   Set in backend/.env (locally) and in Render's Environment tab (deployed):
     RESEND_API_KEY=re_your_key_here

2. Gmail SMTP - used as a fallback when RESEND_API_KEY isn't set. Works fine for
   local development (your own laptop's network isn't blocked), which is why this
   worked in local testing earlier. Requires a Gmail "app password", not your real
   password - set up at https://myaccount.google.com/apppasswords (needs 2FA
   enabled first).
   Set in backend/.env:
     EMAIL_ADDRESS=youraddress@gmail.com
     EMAIL_APP_PASSWORD=your_16_char_app_password
"""
import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", "HealthLoop <onboarding@resend.dev>")

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _send_email(to_email: str, subject: str, body: str, log_label: str) -> bool:
    """Shared sender used by both reminder and parent-notification emails.
    Returns True if sent successfully, False otherwise (never raises - a failed
    email should not crash whatever background job or request called this)."""

    if RESEND_API_KEY:
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": RESEND_FROM,
                    "to": [to_email],
                    "subject": subject,
                    "text": body,
                },
                timeout=10,
            )
            if response.status_code in (200, 201):
                return True
            print(f"[email_service] Resend failed to send {log_label} to {to_email}: "
                  f"{response.status_code} {response.text}")
            return False
        except Exception as e:
            print(f"[email_service] Resend request failed for {log_label} to {to_email}: {e}")
            return False

    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        print(f"[email_service] Neither RESEND_API_KEY nor EMAIL_ADDRESS/EMAIL_APP_PASSWORD "
              f"configured - skipping {log_label} email.")
        return False

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
        print(f"[email_service] SMTP failed to send {log_label} to {to_email}: {e}")
        return False


def send_reminder_email(to_email: str, patient_name: str, medicine_name: str, dosage: str, frequency: str) -> bool:
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

    return _send_email(to_email, subject, body, log_label="reminder")


def send_parent_notification_email(to_email: str, student_name: str, language: str = "English") -> bool:
    """
    Sent only when a student in a mental-health check-in shows signs of real risk
    AND explicitly consents to a parent/guardian being notified - this is never
    triggered silently or without the student's knowledge (see mental-health.html's
    consent flow). Deliberately calm and non-alarmist in tone, and does not repeat
    what the student said - it invites the parent to reach out and talk, not
    frighten them with detail we can't respond to.
    """
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

    return _send_email(to_email, subject, body, log_label="parent notification")
