"""
Sends reminder and parent-notification emails.

Three delivery paths, tried in this order:

1. Brevo (HTTP API, port 443) - used automatically whenever BREVO_API_KEY is set.
   THIS IS THE RECOMMENDED OPTION for sending to real patients/multiple test
   accounts: unlike Resend below, Brevo only requires verifying a single SENDER
   EMAIL ADDRESS (a quick email-link click, no domain/DNS setup needed) - once
   that's done, you can send to ANY recipient. Free tier: 300 emails/day.
   Get a free key at https://app.brevo.com (Settings -> SMTP & API -> API Keys),
   then verify a sender under Settings -> Senders & IP -> Senders (use any email
   you can receive mail at - your own Gmail is fine).
   Set in backend/.env (locally) and in Render's Environment tab (deployed):
     BREVO_API_KEY=xkeysib-your_key_here
     BREVO_SENDER_EMAIL=the_email_you_verified_in_brevo@example.com

2. Resend (HTTP API, port 443) - used automatically whenever RESEND_API_KEY is set
   AND Brevo isn't configured. Get a free key at https://resend.com (no card
   required). IMPORTANT limitation on Resend's free/unverified tier: without
   verifying a whole DOMAIN (not just an email - real DNS setup), you can only
   send TO the email address you signed up to Resend with, no other recipients -
   this is why reminders worked for your own account but silently failed (403)
   for every other test account. Brevo above avoids this restriction.
   Set in backend/.env:
     RESEND_API_KEY=re_your_key_here

Both HTTP options above exist because Render's free tier blocks outbound SMTP
connections (ports 587/465/25) as a standard anti-abuse measure - that's why
Gmail SMTP below fails on Render with "Network is unreachable", even with
correct credentials. That error is Render's firewall, not a code problem.

3. Gmail SMTP - used as a last-resort fallback when neither BREVO_API_KEY nor
   RESEND_API_KEY is set. Works fine for local development (your own laptop's
   network isn't blocked the way Render's is). Requires a Gmail "app password",
   not your real password - set up at https://myaccount.google.com/apppasswords
   (needs 2FA enabled first).
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

from groq_client import translate_text

load_dotenv()

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "")
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "HealthLoop")

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

    if BREVO_API_KEY:
        if not BREVO_SENDER_EMAIL:
            print(f"[email_service] BREVO_API_KEY is set but BREVO_SENDER_EMAIL is missing - "
                  f"skipping {log_label} email. Set BREVO_SENDER_EMAIL to the address you verified in Brevo.")
            return False
        try:
            response = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": BREVO_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "sender": {"email": BREVO_SENDER_EMAIL, "name": BREVO_SENDER_NAME},
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "textContent": body,
                },
                timeout=10,
            )
            if response.status_code in (200, 201):
                return True
            print(f"[email_service] Brevo failed to send {log_label} to {to_email}: "
                  f"{response.status_code} {response.text}")
            return False
        except Exception as e:
            print(f"[email_service] Brevo request failed for {log_label} to {to_email}: {e}")
            return False

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


def send_reminder_email(to_email: str, patient_name: str, medicine_name: str, dosage: str, frequency: str, language: str = "English") -> bool:
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

    subject = translate_text(subject, language)
    body = translate_text(body, language)

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

    # Note: this uses the STUDENT's selected language as a best-effort default,
    # since there's no separate language preference stored for the parent/guardian.
    # If the parent's actual preferred language differs, this may not match -
    # a known limitation given the current data model.
    subject = translate_text(subject, language)
    body = translate_text(body, language)

    return _send_email(to_email, subject, body, log_label="parent notification")


def send_otp_email(to_email: str, otp_code: str, language: str = "English") -> bool:
    """Sends a 6-digit one-time password for the forgot-password flow. Valid for
    10 minutes (enforced in main.py, not here) - this function only sends it."""
    subject = "Your HealthLoop password reset code"
    body = (
        f"Hello,\n\n"
        f"Your one-time code to reset your HealthLoop password is:\n\n"
        f"    {otp_code}\n\n"
        f"This code expires in 10 minutes. If you didn't request a password reset, "
        f"you can safely ignore this email.\n\n"
        f"- HealthLoop"
    )
    subject = translate_text(subject, language)
    body = translate_text(body, language)
    return _send_email(to_email, subject, body, log_label="password reset OTP")
