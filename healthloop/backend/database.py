"""
HealthLoop database layer - SQLAlchemy ORM.

Switch databases by setting DATABASE_URL in backend/.env - nothing else needs to change.

Examples:
  SQLite (default, zero setup):
    DATABASE_URL=sqlite:///./healthloop.db

  PostgreSQL:
    DATABASE_URL=postgresql://username:password@localhost:5432/healthloop
    (pip install psycopg2-binary - already in requirements.txt)

  MySQL (e.g. Aiven, PlanetScale - most require SSL):
    DATABASE_URL=mysql+pymysql://username:password@host:port/database_name
    (pip install pymysql - already in requirements.txt)
    Do NOT add "?ssl=true" or "?ssl-mode=REQUIRED" to the URL itself - SSL is
    handled automatically below via connect_args for any mysql+pymysql:// URL.

For a free hosted PostgreSQL (no local install needed) for your final demo/judging setup,
services like Supabase, Neon, or Railway all offer a free tier - just paste their
connection string in as DATABASE_URL.
"""
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean
)
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# Two ways to configure the database connection:
#
# 1. DATABASE_URL - a full connection string. If your password has special
#    characters (@, #, %, etc.), you must percent-encode them yourself, which
#    is easy to get wrong (e.g. "%40" not "%%40" - the doubling only applies
#    inside .bat script files, never at an interactive Command Prompt or in a
#    plain .env file).
#
# 2. DB_USER / DB_PASSWORD / DB_HOST / DB_PORT / DB_NAME / DB_DRIVER - set
#    these instead, and the URL is built safely below using SQLAlchemy's own
#    URL.create(), which handles special characters in the password
#    automatically. This is the recommended, foolproof option - use this one
#    if you've had trouble with DATABASE_URL directly.
_raw_database_url = os.getenv("DATABASE_URL")

if _raw_database_url:
    DATABASE_URL = _raw_database_url
elif os.getenv("DB_USER"):
    DATABASE_URL = URL.create(
        drivername=os.getenv("DB_DRIVER", "postgresql"),
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "healthloop"),
    )
else:
    DATABASE_URL = f"sqlite:///{BASE_DIR}/healthloop.db"

# Connection args differ by database type:
# - SQLite needs this for use with FastAPI's threaded requests.
# - MySQL (e.g. Aiven, PlanetScale) commonly requires SSL - PyMySQL needs this
#   passed as a dict here, NOT as a "?ssl=true" query param in the URL (that
#   syntax silently breaks PyMySQL's connection args parsing).
_drivername = DATABASE_URL.drivername if hasattr(DATABASE_URL, "drivername") else str(DATABASE_URL)

if _drivername.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif _drivername.startswith("mysql"):
    connect_args = {"ssl": {"ssl": {}}}
else:
    connect_args = {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    parent_phone = Column(String(20), nullable=True)
    parent_email = Column(String(255), nullable=True)
    age = Column(Integer, nullable=True)
    language = Column(String(50), default="English")
    created_at = Column(DateTime, default=datetime.utcnow)

    reports = relationship("Report", back_populates="user")
    reminders = relationship("Reminder", back_populates="user")


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    raw_text = Column(Text)
    primary_finding = Column(Text)   # JSON stored as text (works identically across SQLite/Postgres/MySQL)
    other_findings = Column(Text)    # JSON stored as text
    normal_findings = Column(Text)   # JSON stored as text - list of values that came back fine
    diet_tips = Column(Text)         # JSON stored as text
    diet_plan = Column(Text)         # JSON stored as text - day-by-day meal plan (Monday..Sunday)
    language = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reports")


class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    medicine_name = Column(String(255), nullable=True)   # optional - user can skip straight to just a time
    dosage = Column(String(255), nullable=True)           # optional
    frequency = Column(String(255), nullable=True)         # optional
    reminder_time = Column(String(5), nullable=True)        # "HH:MM" 24-hour format
    last_emailed_date = Column(String(10), nullable=True)    # "YYYY-MM-DD" - prevents re-sending same day
    taken = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reminders")


class Checkin(Base):
    __tablename__ = "checkins"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    question = Column(Text)
    answer = Column(Text)
    severity = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


class MentalHealthSession(Base):
    __tablename__ = "mental_health_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    message = Column(Text)
    role = Column(String(20))
    risk_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency - yields a session, closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized. Using: {DATABASE_URL}")
