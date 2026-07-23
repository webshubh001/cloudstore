"""
Test CloudStore share email delivery to kartikswan001@gmail.com
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cloudstore.settings')
django.setup()

from django.core.mail import EmailMultiAlternatives
from django.conf import settings

print("=" * 60)
print("CloudStore Share Email - Direct Test")
print("=" * 60)
print("EMAIL_BACKEND :", settings.EMAIL_BACKEND)
print("EMAIL_HOST    :", settings.EMAIL_HOST)
print("EMAIL_PORT    :", settings.EMAIL_PORT)
print("EMAIL_USER    :", settings.EMAIL_HOST_USER)
print("FROM_EMAIL    :", settings.DEFAULT_FROM_EMAIL)
print()

TO_EMAIL = "kartikswan001@gmail.com"
sender_name = "Shubham"
file_name = "menu.html"
share_url = "http://127.0.0.1:8000/share/test-token-direct-123/"
expiry_str = "Never"
permission_label = "View & Download"

plain_body = (
    "{} shared a file with you via CloudStore.\n\n"
    "File: {}\n"
    "Access: {}\n"
    "Expires: {}\n\n"
    "Open link: {}\n\n"
    "-- CloudStore Team"
).format(sender_name, file_name, permission_label, expiry_str, share_url)

html_body = """<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#f4f4f7;margin:0;padding:20px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;">
  <div style="background:linear-gradient(135deg,#7c3aed,#a855f7);padding:28px 36px;text-align:center;">
    <h1 style="color:#fff;margin:0;font-size:22px;">CloudStore</h1>
    <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:13px;">Secure Cloud File Sharing</p>
  </div>
  <div style="padding:32px 36px;">
    <p style="color:#374151;font-size:15px;margin-bottom:20px;">
      Hi there! <strong>{sender}</strong> has shared a file with you on <strong>CloudStore</strong>.
    </p>
    <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:18px 22px;margin-bottom:24px;">
      <p style="font-weight:700;font-size:16px;color:#111827;margin:0 0 4px;">{file}</p>
      <p style="font-size:13px;color:#6b7280;margin:0;">Access: {perm} | Expires: {exp}</p>
    </div>
    <a href="{url}" style="display:block;background:linear-gradient(135deg,#7c3aed,#a855f7);color:#fff;
       text-decoration:none;text-align:center;padding:14px;border-radius:8px;font-weight:600;font-size:15px;margin-bottom:20px;">
      Open Shared File
    </a>
  </div>
  <div style="background:#f9fafb;text-align:center;padding:14px;font-size:12px;color:#9ca3af;">
    You received this because someone shared a CloudStore file with you.
  </div>
</div>
</body>
</html>""".format(
    sender=sender_name, file=file_name,
    perm=permission_label, exp=expiry_str, url=share_url
)

from_addr = "CloudStore <{}>".format(settings.EMAIL_HOST_USER)
subject = '{} shared "{}" with you - CloudStore'.format(sender_name, file_name)

print("Sending FROM :", from_addr)
print("Sending TO   :", TO_EMAIL)
print("Subject      :", subject)
print()
print("Connecting to Gmail SMTP...")

try:
    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_body,
        from_email=from_addr,
        to=[TO_EMAIL],
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=False)
    print()
    print("[RESULT] SUCCESS - Email sent!")
    print("  Check the INBOX of:", TO_EMAIL)
    print("  Also check the SPAM folder if not in inbox.")
    sys.exit(0)
except Exception as e:
    import traceback
    print()
    print("[RESULT] FAILED -", type(e).__name__)
    print("  Error:", str(e))
    print()
    traceback.print_exc()
    sys.exit(1)
