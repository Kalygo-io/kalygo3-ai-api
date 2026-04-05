"""
Seed script — inserts one "Welcome Email" template for account_id=1.

Usage (from kalygo3-ai-api directory):
    python -m scripts.seed_welcome_template
    python -m scripts.seed_welcome_template --account-id 2
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.db.database import SessionLocal
from src.db.models import EmailTemplate

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>{{subject}}</title>
</head>
<body style="margin:0;padding:0;background-color:#f0f4f8;font-family:Arial,Helvetica,sans-serif;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <!-- Preheader (hidden preview text) -->
  <span style="display:none;font-size:1px;color:#f0f4f8;max-height:0;max-width:0;opacity:0;overflow:hidden;">{{preheader}}</span>

  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f0f4f8;">
    <tr>
      <td align="center" style="padding:32px 16px;">

        <!-- Card -->
        <table width="600" cellpadding="0" cellspacing="0" border="0"
               style="background-color:#ffffff;border-radius:10px;overflow:hidden;max-width:600px;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

          <!-- Header -->
          <tr>
            <td style="background-color:#0f172a;padding:28px 40px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <p style="margin:0;font-size:22px;font-weight:700;color:#ffffff;letter-spacing:-0.3px;">
                      {{company_name}}
                    </p>
                  </td>
                  <td align="right">
                    <p style="margin:0;font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;">
                      Welcome
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Hero band -->
          <tr>
            <td style="background-color:#4f46e5;padding:4px 0;"></td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:40px 40px 32px;">
              <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#6366f1;text-transform:uppercase;letter-spacing:0.8px;">
                Hello, {{first_name}} 👋
              </p>
              <p style="margin:0 0 24px;font-size:26px;font-weight:700;color:#0f172a;line-height:1.25;">
                Welcome aboard.
              </p>
              <p style="margin:0 0 24px;font-size:16px;line-height:1.7;color:#475569;">
                {{body}}
              </p>

              <!-- CTA Button -->
              <table cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 32px;">
                <tr>
                  <td style="background-color:#4f46e5;border-radius:8px;padding:14px 28px;text-align:center;">
                    <a href="{{cta_url}}"
                       style="color:#ffffff;text-decoration:none;font-weight:700;font-size:15px;font-family:Arial,Helvetica,sans-serif;display:inline-block;">
                      {{cta_label}}
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin:0;font-size:14px;color:#94a3b8;">
                If the button doesn't work, copy this link into your browser:<br>
                <a href="{{cta_url}}" style="color:#6366f1;word-break:break-all;">{{cta_url}}</a>
              </p>
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="border-top:1px solid #e2e8f0;font-size:0;">&nbsp;</td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:24px 40px;background-color:#f8fafc;border-radius:0 0 10px 10px;">
              <p style="margin:0 0 4px;font-size:12px;color:#94a3b8;text-align:center;">
                © 2026 {{company_name}} · All rights reserved
              </p>
              <p style="margin:0;font-size:12px;color:#cbd5e1;text-align:center;">
                You received this email because you signed up at {{company_name}}.
              </p>
            </td>
          </tr>

        </table>
        <!-- /Card -->

      </td>
    </tr>
  </table>
</body>
</html>
"""

VARIABLES = [
    {"name": "subject",       "label": "Email subject",      "default": "Welcome to {{company_name}}"},
    {"name": "preheader",     "label": "Preheader text",     "default": "We're glad to have you here."},
    {"name": "company_name",  "label": "Company name",       "default": "Kalygo"},
    {"name": "first_name",    "label": "Recipient first name","default": "there"},
    {"name": "body",          "label": "Main body copy",     "default": "We're thrilled to have you with us. Click the button below to get started and explore everything we have to offer."},
    {"name": "cta_url",       "label": "CTA button URL",     "default": "https://kalygo.io"},
    {"name": "cta_label",     "label": "CTA button label",   "default": "Get Started →"},
]


def seed(account_id: int) -> None:
    db = SessionLocal()
    try:
        existing = (
            db.query(EmailTemplate)
            .filter(
                EmailTemplate.account_id == account_id,
                EmailTemplate.name == "Welcome Email",
            )
            .first()
        )
        if existing:
            print(f"ℹ️  Template 'Welcome Email' already exists for account {account_id} (id={existing.id}). Skipping.")
            return

        tmpl = EmailTemplate(
            account_id=account_id,
            name="Welcome Email",
            description="A clean, professional welcome email sent to new users after sign-up.",
            subject_template="Welcome to {{company_name}}, {{first_name}}!",
            html_template=HTML_TEMPLATE.strip(),
            variables=VARIABLES,
        )
        db.add(tmpl)
        db.commit()
        db.refresh(tmpl)
        print(f"✅  Created 'Welcome Email' template — id={tmpl.id}, account_id={account_id}")
    except Exception as e:
        db.rollback()
        print(f"❌  Failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed a Welcome Email template")
    parser.add_argument("--account-id", type=int, default=1,
                        help="Account ID to create the template for (default: 1)")
    args = parser.parse_args()
    seed(args.account_id)
