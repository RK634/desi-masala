"""Small SMTP helper. Email failure must never roll back an already committed order update."""
import os
import smtplib
import ssl
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

def send_email(recipient: str, subject: str, body: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "465"))
    username = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", username or "")
    if not all([host, username, password, sender, recipient]):
        raise RuntimeError("SMTP email delivery is not configured")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as server:
            server.login(username, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(username, password)
            server.send_message(msg)

def send_order_status_email(recipient: str, order_id: int, status: str, carrier=None, tracking_number=None, tracking_url=None, eta=None) -> None:
    subject = f"Desi Masala order #{order_id}: {status.replace('_', ' ').title()}"
    lines = [f"Your Desi Masala order #{order_id} status is now {status.replace('_', ' ').lower()}."]
    if carrier: lines.append(f"Courier: {carrier}")
    if tracking_number: lines.append(f"Tracking number: {tracking_number}")
    if tracking_url: lines.append(f"Track your parcel: {tracking_url}")
    if eta: lines.append(f"Estimated delivery: {eta}")
    lines.append("You can also view the latest status in Your Account → Orders & tracking.")
    send_email(recipient, subject, "\n\n".join(lines))
