import datetime
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SENDER_EMAIL

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from datetime import timezone, timedelta
    ZoneInfo = None

logger = logging.getLogger("attendance.email")

def get_ist_now() -> datetime.datetime:
    """Returns the current time in Asia/Kolkata timezone, safe for cloud deployments."""
    if ZoneInfo is not None:
        return datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
    # Fallback if zoneinfo is somehow missing (e.g. older python)
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))

def get_year_label(yr: int | None = None, sec: str | None = None) -> str:
    """Helper to convert year number or section code into standard label (e.g. 1st Year)."""
    if yr and yr in (1, 2, 3, 4):
        suffixes = {1: "1st Year", 2: "2nd Year", 3: "3rd Year", 4: "4th Year"}
        return suffixes.get(yr, f"Year {yr}")
    if sec and len(sec) >= 2 and sec[1] in ("1", "2", "3", "4"):
        y = int(sec[1])
        suffixes = {1: "1st Year", 2: "2nd Year", 3: "3rd Year", 4: "4th Year"}
        return suffixes.get(y, f"Year {y}")
    return "N/A"

def send_email_otp(recipient_email: str, otp_code: str, recipient_name: str = "Faculty Member") -> bool:
    """Send OTP email via SMTP or print to log/console as fallback."""
    subject = f"🔑 Password Reset OTP: {otp_code} — IERT Attendance Portal"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #0b1324; color: #e2e8f0; margin: 0; padding: 20px; }}
            .container {{ max-width: 480px; margin: 0 auto; background: #141d33; padding: 30px; border-radius: 12px; border: 1px solid #1f2d4d; box-shadow: 0 8px 24px rgba(0,0,0,0.4); }}
            .brand {{ color: #3b82f6; font-size: 22px; font-weight: bold; margin-top: 0; margin-bottom: 4px; }}
            .sub-title {{ color: #94a3b8; font-size: 13px; margin-bottom: 24px; }}
            .otp-box {{ background: #1e293b; color: #38bdf8; font-size: 32px; font-weight: bold; letter-spacing: 8px; text-align: center; padding: 18px; border-radius: 8px; margin: 24px 0; border: 1px solid #334155; }}
            .warning {{ font-size: 13px; color: #94a3b8; line-height: 1.5; }}
            .footer {{ font-size: 11px; color: #64748b; text-align: center; margin-top: 24px; border-top: 1px solid #1f2d4d; padding-top: 16px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="brand">IERT PRAYAGRAJ</div>
            <div class="sub-title">Smart Attendance System &bull; Password Reset</div>
            <p>Hello <strong>{recipient_name}</strong>,</p>
            <p>We received a request to reset your password for your faculty account (<code>{recipient_email}</code>).</p>
            <p>Your 6-digit One-Time Password (OTP) is:</p>
            <div class="otp-box">{otp_code}</div>
            <p class="warning">⚠️ This OTP is valid for <strong>10 minutes</strong>. Do NOT share this code with anyone.</p>
            <div class="footer">If you did not request a password reset, you can safely ignore this email.<br>&copy; IERT Prayagraj Attendance Portal</div>
        </div>
    </body>
    </html>
    """
    
    # Try sending via SMTP if credentials are configured
    if SMTP_USER and SMTP_PASSWORD and SMTP_USER != "your_email@gmail.com":
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SENDER_EMAIL or SMTP_USER
            msg["To"] = recipient_email
            
            msg.attach(MIMEText(html_content, "html"))
            
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(msg["From"], [recipient_email], msg.as_string())
            
            logger.info(f"Successfully sent OTP email via SMTP to {recipient_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via SMTP ({e}). Logged to server console.")

    # Fallback to server log & console output
    logger.info(f"========== [DEV OTP NOTIFICATION] ==========")
    logger.info(f"Recipient Email: {recipient_email}")
    logger.info(f"OTP Code: {otp_code}")
    logger.info(f"============================================")
    print(f"\n🔑 [OTP LOG] Password Reset OTP for '{recipient_email}': {otp_code}\n")
    return False
