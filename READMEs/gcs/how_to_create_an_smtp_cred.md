## Step 1 — Enable 2-Step Verification (if not already on)

Go to myaccount.google.com/security
Under "How you sign in to Google," click 2-Step Verification
Follow the prompts to enable it

## Step 2 — Generate an App Password

Go to myaccount.google.com/apppasswords
If you don't see this page, 2-Step Verification is not yet enabled
In the "App name" field, type something descriptive like Kalygo SMTP
Click Create
Google shows you a 16-character password (formatted as xxxx xxxx xxxx xxxx)
Copy it immediately — Google will never show it again

## Step 3 — Add the credential in Kalygo

In the Credentials page, create a new credential:
Service Name: Google Gmail (SMTP)
From Email: your full Gmail address (e.g. you@gmail.com or you@yourdomain.com if it's a Google Workspace account)
App Password: the 16-character code from Step 2 (spaces are fine, they're ignored by the SMTP library)
Notes
If you're using Google Workspace (custom domain), the steps are identical — the App Password is generated from the user's Google account, not from Google Cloud Console
The App Password authenticates against Gmail's SMTP server (smtp.gmail.com:465) on behalf of the from_email address
You can revoke the App Password at any time from myaccount.google.com/apppasswords without affecting your main account password
There's no Google Cloud Console setup required — no OAuth client, no redirect URIs, no API enablement