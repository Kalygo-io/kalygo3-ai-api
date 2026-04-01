# TLDR

How to create an OAuth cred

##

Go to `APIs & Services` > `Credentials` >

https://console.cloud.google.com/apis/credentials?project=kalygo-436411

##

Create `OAuth Client ID`

- Application type: `Web application`
- 

##

### Enable the Gmail API

- Go to console.cloud.google.com
- Select or create a project
- Navigate to APIs & Services → Library
- Search for Gmail API and click Enable

### Create OAuth 2.0 Credentials

- Go to APIs & Services → Credentials
- Click + Create Credentials → OAuth client ID
- Application type: Web application (or Desktop app for testing)
- Add an authorized redirect URI — for local token generation, http://localhost works
- Click Create — you'll get your client_id and client_secret

### Configure the OAuth Consent Screen

- Go to APIs & Services → OAuth consent screen
- Add the scope: https://www.googleapis.com/auth/gmail.send
- Add your Gmail address as a test user (if app is in "Testing" mode)

### Generate the refresh token

- The easiest way is to use Google's OAuth Playground:
- Go to developers.google.com/oauthplayground
- Click the gear icon → check "Use your own OAuth credentials" → enter your client_id and client_secret
- In the scope list, find Gmail API v1 and select https://www.googleapis.com/auth/gmail.send
- Click Authorize APIs → sign in with the Gmail account you want to send from
- Click Exchange authorization code for tokens
- Copy the refresh token from the response

##

curl -X POST https://oauth2.googleapis.com/token \
  -d "client_id=<CLIENT_ID>" \
  -d "client_secret=<CLIENT_SECRET>" \
  -d "refresh_token=<REFRESH_TOKEN>" \
  -d "grant_type=refresh_token"