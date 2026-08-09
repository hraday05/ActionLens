import os
import ssl
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587  # STARTTLS port (more firewall-friendly than 465)


OTP_EXPIRY_MINUTES = 10

def generate_otp() -> str:
    """Generates a secure 6-digit OTP."""
    return ''.join(random.choices(string.digits, k=6))

def get_otp_expiry() -> str:
    """Returns ISO timestamp for OTP expiry (10 minutes from now)."""
    return (datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()

def send_otp_email(to_email: str, otp: str, username: str) -> bool:
    """
    Sends OTP verification email via Gmail SMTP.
    Returns True on success, False on failure.
    If SMTP not configured, prints OTP to terminal for local testing.
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        # Graceful degradation for local testing
        print("\n" + "="*50)
        print(f"  ⚠️  SMTP NOT CONFIGURED — LOCAL TESTING MODE")
        print(f"  📧 OTP for {username} ({to_email}): {otp}")
        print(f"  ⏰ Expires in {OTP_EXPIRY_MINUTES} minutes")
        print("="*50 + "\n")
        return True  # Treat as success so the flow continues

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🔐 Your ActionLens OTP: {otp}"
        msg["From"] = SMTP_EMAIL
        msg["To"] = to_email

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Inter', -apple-system, sans-serif; background: #0f172a; margin: 0; padding: 20px; }}
    .container {{ max-width: 480px; margin: 0 auto; background: #1e293b; border-radius: 16px; overflow: hidden; border: 1px solid #334155; }}
    .header {{ background: linear-gradient(135deg, #2563eb, #4f46e5); padding: 32px; text-align: center; }}
    .logo {{ font-size: 28px; font-weight: 900; color: white; letter-spacing: -1px; }}
    .tagline {{ color: #bfdbfe; font-size: 12px; margin-top: 4px; }}
    .body {{ padding: 32px; }}
    .greeting {{ color: #94a3b8; font-size: 14px; margin-bottom: 24px; }}
    .otp-label {{ color: #64748b; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 12px; }}
    .otp-box {{ background: #0f172a; border: 2px solid #2563eb; border-radius: 12px; padding: 24px; text-align: center; }}
    .otp-code {{ font-size: 42px; font-weight: 900; color: #60a5fa; letter-spacing: 10px; font-family: 'Courier New', monospace; }}
    .expiry {{ color: #64748b; font-size: 12px; margin-top: 16px; text-align: center; }}
    .warning {{ background: #1c1917; border-left: 3px solid #f59e0b; border-radius: 8px; padding: 12px 16px; margin-top: 24px; color: #d97706; font-size: 12px; }}
    .footer {{ text-align: center; padding: 16px 32px 24px; color: #475569; font-size: 11px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo">ActionLens 🔍</div>
      <div class="tagline">AI-Powered Document Action Planner</div>
    </div>
    <div class="body">
      <p class="greeting">Hi <strong style="color:#e2e8f0">{username}</strong>, welcome to ActionLens!</p>
      <div class="otp-label">Your verification code</div>
      <div class="otp-box">
        <div class="otp-code">{otp}</div>
      </div>
      <p class="expiry">⏰ This code expires in <strong style="color:#f8fafc">{OTP_EXPIRY_MINUTES} minutes</strong></p>
      <div class="warning">
        ⚠️ Never share this code. ActionLens will never ask for your OTP via chat or phone.
      </div>
    </div>
    <div class="footer">
      If you didn't request this code, you can safely ignore this email.<br>
      &copy; 2026 ActionLens — Devengers Hackathon
    </div>
  </div>
</body>
</html>
"""
        text_body = f"Your ActionLens OTP is: {otp}\nIt expires in {OTP_EXPIRY_MINUTES} minutes.\nDo not share this code with anyone."

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())

        print(f"✅ OTP email sent to {to_email}")
        return True

    except Exception as e:
        print(f"❌ Failed to send OTP email: {e}")
        # Fall back to terminal print so dev can still test
        print(f"\n[FALLBACK] OTP for {username}: {otp}\n")
        return False
