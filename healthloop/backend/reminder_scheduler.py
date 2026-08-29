"""
Runs inside the FastAPI process, checking every minute for reminders that are
due, and emailing the patient.

Uses last_emailed_date to send at most once per reminder per day, so it
doesn't re-fire repeatedly once it's already sent for today.

Note: like the reminder feature itself, this only runs while the backend
process is alive. On Render's free tier, the service spins down after
inactivity and only wakes on the next incoming request - so a reminder due
at, say, 15:17 while the process was asleep won't fire at exactly 15:17.
To handle this without needing a paid always-on tier, _check_and_send_reminders
below matches any reminder whose time is due-or-already-passed-today (not an
exact-minute match), and start_scheduler runs one check immediately on
startup - so the very next time the process wakes up (from any visitor
hitting the site), it catches up on anything that was missed while asleep,
rather than requiring the exact minute to land while already running.
For reminders to arrive close to their actual scheduled time rather than
"whenever someone next visits", pair this with a free uptime pinger (e.g.
UptimeRobot or cron-job.org) hitting your Render URL every 5-10 minutes to
keep the service from sleeping in the first place - this code fixes
correctness (nothing gets silently skipped forever) but can't fix a
completely idle service waking itself up with no visitor and no pinger.

IMPORTANT - timezone: reminder_time is entered by users as their local India
time (e.g. "15:17"), but cloud hosts like Render run their servers in UTC, not
IST. Comparing against datetime.now() would use the SERVER's timezone, which
silently never matches what the user typed - the reminder just never fires,
with no error anywhere, since nothing actually failed. IST is forced explicitly
here so this works the same locally (where the machine happens to already be on
IST) and in the cloud (where it very likely isn't).
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler

from database import SessionLocal, Reminder, User
from email_service import send_reminder_email

IST = ZoneInfo("Asia/Kolkata")
scheduler = BackgroundScheduler()


def _check_and_send_reminders():
    now = datetime.now(IST)
    current_time = now.strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")

    db = SessionLocal()
    try:
        due = (
            db.query(Reminder)
            .filter(Reminder.reminder_time <= current_time)  # due now OR already passed today - catches up after sleep
            .filter(Reminder.taken == False)  # noqa: E712
            .all()
        )
        for reminder in due:
            if reminder.last_emailed_date == today:
                continue  # already emailed for this reminder today

            if not reminder.user_id:
                continue  # no user to email (manually created without a user, shouldn't normally happen)

            user = db.query(User).filter(User.id == reminder.user_id).first()
            if not user or not user.email:
                continue

            sent = send_reminder_email(
                to_email=user.email,
                patient_name=user.name,
                medicine_name=reminder.medicine_name,
                dosage=reminder.dosage,
                frequency=reminder.frequency,
            )
            if sent:
                reminder.last_emailed_date = today
                db.commit()
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(_check_and_send_reminders, "interval", minutes=1, id="reminder_check")
    scheduler.start()
    # Run one check immediately on startup too, not just after the first minute-mark -
    # this is what actually delivers the "catch up on wake" behavior described above.
    _check_and_send_reminders()
