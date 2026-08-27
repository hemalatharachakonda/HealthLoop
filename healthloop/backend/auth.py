"""
Simple password hashing for email/password login.
Uses bcrypt directly - free, no external service, no account needed.

(Not passlib - passlib's bcrypt backend detection has a known compatibility
bug with newer bcrypt versions that throws on setup. Calling bcrypt directly
avoids that entirely and is just as simple.)
"""
import bcrypt


def hash_password(plain_password: str) -> str:
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
