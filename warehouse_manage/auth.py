import hashlib
import os
import secrets
import smtplib
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import quote
import re
import jwt
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal
from pwdlib import PasswordHash
import psycopg
from dotenv import load_dotenv

load_dotenv()

from database import get_connection

router = APIRouter(prefix="/auth", tags=["Authentication"])
password_hasher = PasswordHash.recommended()
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "")

class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=30)
    date_of_birth: date
    address_line1: str = Field(min_length=3, max_length=200)
    postal_code: str = Field(min_length=2, max_length=20)
    city: str = Field(min_length=2, max_length=100)
    country: str = Field(default="Germany", min_length=2, max_length=80)
    marketing_opt_in: bool = False
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        digits = re.sub(r"\D", "", value)
        if len(digits) < 7 or len(digits) > 15 or not re.fullmatch(r"\+?[0-9() .\-/]+", value):
            raise ValueError("Enter a valid phone number including country code, for example +49 151 23456789.")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain a lowercase letter.")
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain an uppercase letter.")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain a number.")
        if not re.search(r"[^A-Za-z0-9]", value):
            raise ValueError("Password must contain a special character.")
        return value

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    account_type: Literal["customer", "admin"] = "customer"
    remember_me: bool = True

def _now_naive_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _send_verification_email(email: str, token: str, code: str):
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM]):
        raise RuntimeError("SMTP email delivery is not configured.")

    link = f"{APP_BASE_URL}/auth/verify?token={quote(token)}"

    message = EmailMessage()
    message["Subject"] = "Verify your Desi Masala account"
    message["From"] = SMTP_FROM
    message["To"] = email
    message.set_content(
        "Welcome to Desi Masala!\n\n"
        f"Your email verification code is: {code}\n\n"
        "Verify using this link:\n"
        f"{link}\n\n"
        "The code and link expire in 30 minutes."
    )

    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(
            SMTP_HOST, SMTP_PORT, timeout=20
        ) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
    else:
        with smtplib.SMTP(
            SMTP_HOST, SMTP_PORT, timeout=20
        ) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)

def _create_access_token(user_id: int, email: str, expires_in_minutes: int) -> str:
    if not JWT_SECRET_KEY or len(JWT_SECRET_KEY) < 32:
        raise HTTPException(status_code=503, detail="Authentication is not configured. Set a strong JWT_SECRET_KEY in the backend .env file.")
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "email": email, "iat": now, "exp": now + timedelta(minutes=expires_in_minutes)}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

@router.post("/register", status_code=201)
def register_customer(data: RegisterRequest):
    email = str(data.email).strip().lower()
    name = data.name.strip()
    phone = data.phone.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required.")
    if data.date_of_birth and data.date_of_birth > date.today():
        raise HTTPException(status_code=400, detail="Birthday cannot be in the future.")
    # Email and phone uniqueness are checked before insert for clear errors; unique
    # indexes in the schema remain the final protection against concurrent requests.
    with get_connection() as conn:
        duplicate = conn.execute(
            "SELECT email, phone FROM public.users WHERE lower(email)=%s OR regexp_replace(COALESCE(phone,''), '[^0-9]', '', 'g')=regexp_replace(%s, '[^0-9]', '', 'g') LIMIT 1",
            (email, phone),
        ).fetchone()
    if duplicate:
        if duplicate["email"] and duplicate["email"].strip().lower() == email:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        raise HTTPException(status_code=409, detail="An account with this phone number already exists.")

    password_hash = password_hasher.hash(data.password)
    raw_token = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1_000_000):06d}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    now = _now_naive_utc()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.users (name, email, phone, password_hash, date_of_birth, marketing_opt_in, email_verified) VALUES (%s, %s, %s, %s, %s, %s, FALSE) RETURNING id",
                    (name, email, phone, password_hash, data.date_of_birth, data.marketing_opt_in),
                )
                user = cur.fetchone()
                cur.execute(
                    """INSERT INTO public.customer_addresses (user_id,label,recipient_name,phone,address_line1,postal_code,city,country,is_default)
                       VALUES (%s,'Home',%s,%s,%s,%s,%s,%s,TRUE)""",
                    (user["id"], name, phone, data.address_line1.strip(), data.postal_code.strip(), data.city.strip(), data.country.strip()),
                )
                cur.execute(
                    "INSERT INTO public.email_verification_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s), (%s, %s, %s)",
                    (user["id"], token_hash, now + timedelta(minutes=30), user["id"], code_hash, now + timedelta(minutes=30)),
                )
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    try:
        _send_verification_email(email, raw_token, code)
    except Exception:
        # Remove the just-created account/token so the customer can retry after SMTP is fixed.
        # A new account cannot have existing orders at this point.
        with get_connection() as conn:
            conn.execute("DELETE FROM public.email_verification_tokens WHERE token_hash = %s", (token_hash,))
            conn.execute("DELETE FROM public.users WHERE id = %s AND email_verified = FALSE", (user["id"],))
        raise HTTPException(status_code=503, detail="We could not send the verification email. Please try again later or contact support.")
    return {"message": "Registration successful. Check your email to verify your account."}



class ResendVerificationRequest(BaseModel):
    email: EmailStr

@router.post("/resend-verification")
def resend_verification(data: ResendVerificationRequest):
    email = str(data.email).strip().lower()
    now = _now_naive_utc()
    raw_token = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1_000_000):06d}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    with get_connection() as conn:
        user = conn.execute(
            "SELECT id, email_verified FROM public.users WHERE lower(email) = %s", (email,)
        ).fetchone()
        if not user or user["email_verified"]:
            return {"message": "If the account exists and needs verification, a new email will be sent."}
        conn.execute(
            "UPDATE public.email_verification_tokens SET used_at = %s WHERE user_id = %s AND used_at IS NULL",
            (now, user["id"]),
        )
        conn.execute(
            "INSERT INTO public.email_verification_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s), (%s, %s, %s)",
            (user["id"], token_hash, now + timedelta(minutes=30), user["id"], code_hash, now + timedelta(minutes=30)),
        )
    try:
        _send_verification_email(email, raw_token, code)
    except Exception:
        raise HTTPException(status_code=503, detail="We could not send the verification email right now. Please try again later.")
    return {"message": "If the account exists and needs verification, a new email will be sent."}

@router.get("/verify")
def verify_email(token: str = Query(min_length=20, max_length=200)):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = _now_naive_utc()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_id FROM public.email_verification_tokens WHERE token_hash = %s AND used_at IS NULL AND attempt_count < 5 AND expires_at > %s FOR UPDATE",
                (token_hash, now),
            )
            record = cur.fetchone()
            if not record:
                raise HTTPException(status_code=400, detail="Verification link is invalid, expired, or already used.")
            cur.execute("UPDATE public.users SET email_verified = TRUE, email_verified_at = %s, updated_at = %s WHERE id = %s", (now, now, record["user_id"]))
            cur.execute("UPDATE public.email_verification_tokens SET used_at = %s WHERE user_id = %s AND used_at IS NULL", (now, record["user_id"]))
    return {"message": "Email verified successfully. You can now log in."}

class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


@router.post("/verify-code")
def verify_email_code(data: VerifyCodeRequest):
    email = str(data.email).strip().lower()
    code_hash = hashlib.sha256(data.code.encode()).hexdigest()
    now = _now_naive_utc()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM public.users WHERE lower(email)=%s AND email_verified=FALSE FOR UPDATE", (email,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=400, detail="Account not found or email is already verified.")
            cur.execute("""SELECT id FROM public.email_verification_tokens
                WHERE user_id=%s AND token_hash=%s AND used_at IS NULL AND attempt_count<5 AND expires_at>%s FOR UPDATE""",
                (user["id"],code_hash,now))
            token = cur.fetchone()
            if not token:
                cur.execute("""UPDATE public.email_verification_tokens SET attempt_count=attempt_count+1
                    WHERE user_id=%s AND used_at IS NULL AND expires_at>%s AND attempt_count<5""", (user["id"],now))
                conn.commit()
                raise HTTPException(status_code=400, detail="Verification code is invalid, expired, or has reached its attempt limit. Request a new code.")
            cur.execute("UPDATE public.users SET email_verified=TRUE,email_verified_at=%s,updated_at=%s WHERE id=%s",(now,now,user["id"]))
            cur.execute("UPDATE public.email_verification_tokens SET used_at=%s WHERE user_id=%s AND used_at IS NULL",(now,user["id"]))
    return {"message":"Email verified successfully. You can now log in."}


@router.post("/login")
def login_customer(data: LoginRequest):
    email = str(data.email).strip().lower()
    with get_connection() as conn:
        user = conn.execute(
            "SELECT id, name, email, password_hash, email_verified, role FROM public.users WHERE lower(email) = %s",
            (email,),
        ).fetchone()
    # Same message for missing user and wrong password reduces account enumeration.
    if not user or not user["password_hash"] or not password_hasher.verify(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user["email_verified"]:
        raise HTTPException(status_code=403, detail="Please verify your email before logging in.")
    if user["role"] != data.account_type:
        if data.account_type == "admin":
            raise HTTPException(status_code=403, detail="This account does not have administrator access.")
        raise HTTPException(status_code=403, detail="Please use the administrator sign-in option for this account.")
    expires_in_minutes = 30 * 24 * 60 if data.remember_me else JWT_EXPIRE_MINUTES
    access_token = _create_access_token(user["id"], user["email"], expires_in_minutes)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in_minutes * 60,
        "user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]},
    }
