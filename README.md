# J*B — Autonomous Job Application Monitor

J*B is a Python agent that silently watches your Gmail inbox, uses Google Gemini AI to identify and classify job-application emails, and keeps a Google Sheet up to date with the status, key details, and suggested next actions for every application — automatically, every 2 hours.

---

## Features

- Fetches unread primary-category emails from the last 24 hours
- Classifies each email with Gemini 2.5 Flash (interview invite, rejection, follow-up needed, offer received, awaiting response)
- Extracts company, role, recruiter name/email, summary, next action, urgency, and a suggested reply
- Writes results to a Google Sheet with deduplication (updates existing rows instead of creating duplicates)
- Color-codes the Status column: green (offer), red (rejection), yellow (follow-up), blue (interview), grey (awaiting)
- Marks processed emails as read so they are never double-processed
- Runs on a 2-hour loop via APScheduler; also runs once immediately on startup

---

## Project Structure

```
jb/
├── main.py              # Entry point
├── gmail_client.py      # Gmail OAuth2 + email fetching
├── classifier.py        # Gemini classification
├── sheets_client.py     # Google Sheets read/write
├── scheduler.py         # APScheduler loop
├── credentials.json     # (you supply this — never commit it)
├── token.json           # (auto-generated on first run — never commit it)
├── .env                 # API keys and Sheet ID
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Prerequisites

- Python 3.11+
- A Google account with Gmail
- A blank Google Sheet
- A Google Cloud project with the Gmail API and Sheets API enabled
- A Google Gemini API key

---

## Step 1 — Google Cloud Console Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Click the project selector at the top → **New Project** → name it `JB` → **Create**.
3. In the left menu go to **APIs & Services → Library**.
4. Search for **Gmail API** → click it → **Enable**.
5. Search for **Google Sheets API** → click it → **Enable**.
6. Go to **APIs & Services → Credentials** → **Create Credentials → OAuth client ID**.
7. If prompted, configure the OAuth consent screen first:
   - User type: **External**
   - Fill in app name (e.g. `JB`), your email as support and developer contact
   - Add scopes: `.../auth/gmail.modify` and `.../auth/spreadsheets`
   - Add your own Gmail address as a **Test user**
   - Save and continue through to the end
8. Back in **Create OAuth client ID**:
   - Application type: **Desktop app**
   - Name: `JB Desktop`
   - Click **Create**
9. Click **Download JSON** on the confirmation screen (or download it later from the Credentials list).
10. Rename the downloaded file to `credentials.json` and place it in the project root folder.

---

## Step 2 — Create a Google Sheet

1. Go to [sheets.google.com](https://sheets.google.com) and create a new blank spreadsheet.
2. Name it anything you like (e.g. `Job Applications`).
3. Copy the **Sheet ID** from the URL:

```
https://docs.google.com/spreadsheets/d/  <-- THIS PART -->  /edit
```

The Sheet ID is the long string of letters and numbers between `/d/` and `/edit`.

---

## Step 3 — Get a Gemini API Key

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
2. Click **Create API key**.
3. Copy the key.

---

## Step 4 — Configure .env

Open the `.env` file in the project root and fill in your values:

```
GEMINI_API_KEY=your_gemini_api_key_here
SPREADSHEET_ID=your_google_sheet_id_here
```

---

## Step 5 — Install Dependencies

It is recommended to use a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

---

## Step 6 — Run

```bash
python main.py
```

**First run only:** a browser window will open asking you to sign in with your Google account and grant Gmail and Sheets permissions. After you approve, a `token.json` file is saved — you will never be asked to log in again.

After authentication the agent will:

1. Immediately scan your inbox for job-related emails from the last 24 hours
2. Classify each email with Gemini
3. Write results to your Google Sheet
4. Print a summary to the terminal
5. Wait 2 hours and repeat

---

## Google Sheet Columns

| Column | Description |
|---|---|
| Date | Date the email was received |
| Company | Company name extracted by AI |
| Role | Job title extracted by AI |
| Recruiter | Recruiter's name |
| Recruiter Email | Recruiter's email address |
| Status | Application status (color-coded) |
| Summary | One-sentence AI summary of the email |
| Next Action | What you should do next |
| Urgency | high / medium / low |
| Suggested Reply | Draft reply for interview invites and follow-ups |

### Status Color Key

| Color | Meaning |
|---|---|
| Green | Offer received |
| Red | Rejection |
| Yellow | Follow-up needed |
| Blue | Interview invite |
| Grey | Awaiting response |

---

## Troubleshooting

**`credentials.json not found`**
Make sure you downloaded the OAuth client JSON from Google Cloud Console and renamed it exactly to `credentials.json` in the project root.

**`Token has been expired or revoked`**
Delete `token.json` and run `python main.py` again to re-authenticate.

**`SPREADSHEET_ID is not set`**
Check your `.env` file. The ID should be the long string from your Google Sheet URL, not the full URL.

**Gemini returns malformed JSON**
This is handled automatically — the email is skipped and a warning is printed. Gemini 2.5 Flash is generally reliable; retrying on the next run usually works.

**Gmail API 429 rate limit**
Handled automatically with a 5-second retry (up to 3 attempts per email).

**Sheet not updating**
Make sure the Google account you authenticated with has edit access to the spreadsheet. The sheet must also be named `Sheet1` (the default for new spreadsheets).

---

---

## Using a School or Work Email (IMAP)

If your email is a school or work Microsoft 365 account, the Outlook option above likely won't work without IT admin approval. IMAP is the practical alternative — it works with any email provider (school Outlook, Gmail, Yahoo, etc.) using a simple username and app password, with no Azure registration required.

### Step 1 — Enable IMAP on your account

**For school Microsoft 365 / Outlook:**
1. Sign into [outlook.office.com](https://outlook.office.com)
2. Click the gear icon (Settings) → **View all Outlook settings**
3. Go to **Mail → Sync email**
4. Make sure **IMAP** is turned on

**For Gmail (alternative to the OAuth flow):**
1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable 2-Step Verification if not already on
3. Go to **App Passwords** → generate one for "Mail"

### Step 2 — Get an app password

If your account has MFA / two-factor authentication enabled (most school accounts do), you cannot use your regular password. You need an app password:

**Microsoft 365:**
1. Go to [mysignins.microsoft.com/security-info](https://mysignins.microsoft.com/security-info)
2. Click **Add method → App password**
3. Name it `JB` and copy the generated password

> If you don't see "App password" as an option, your school's IT policy may block it. Ask your IT helpdesk to enable app passwords for your account, or use email forwarding to a personal Gmail instead.

### Step 3 — Configure `.env`

```
EMAIL_PROVIDER=imap
IMAP_SERVER=outlook.office365.com   # or imap.gmail.com for Gmail
IMAP_PORT=993
IMAP_USERNAME=your-email@school.edu
IMAP_PASSWORD=your-app-password-here
```

Then run `python main.py` — no browser window will open, it connects directly.

---

## Using Outlook / Microsoft 365 Instead of Gmail

J*B supports both Gmail and Outlook. To switch, set `EMAIL_PROVIDER=outlook` in your `.env`.

> Note: Google Sheets is still used for the tracker regardless of email provider, so you still need `credentials.json` from Google Cloud Console (Step 1 above) for Sheets access.

### Azure App Registration

1. Go to [portal.azure.com](https://portal.azure.com) and sign in.
2. Search for **App registrations** → **New registration**.
3. Name: `JB` — Supported account types: **Accounts in any organizational directory and personal Microsoft accounts** → **Register**.
4. Copy the **Application (client) ID** — this is your `OUTLOOK_CLIENT_ID`.
5. In the left menu go to **Authentication** → **Add a platform → Mobile and desktop applications**.
6. Check the box for `https://login.microsoftonline.com/common/oauth2/nativeclient` → **Configure**.
7. Under **Advanced settings** set **Allow public client flows** to **Yes** → **Save**.
8. In the left menu go to **API permissions → Add a permission → Microsoft Graph → Delegated permissions**.
9. Search for and add `Mail.ReadWrite` → **Add permissions**.
10. Click **Grant admin consent** (if prompted — only needed for work/school accounts).

### Configure `.env` for Outlook

```
EMAIL_PROVIDER=outlook
OUTLOOK_CLIENT_ID=your-azure-app-client-id
OUTLOOK_TENANT_ID=common          # use "common" for personal accounts
                                   # use your tenant ID for work/school accounts
```

Leave the Gmail-related `credentials.json` in place — it is still used for Google Sheets.

### First Outlook Run

A browser window will open asking you to sign into your Microsoft account. After approving, `outlook_token.json` is saved and you will not be asked again for ~90 days.

---

---

## Deploying to the Cloud (Railway)

Running J*B locally means it stops when you close your laptop. Deploy it to [Railway](https://railway.app) to keep it running 24/7 for free.

### Why Railway?

- Free tier with $5/month credit (more than enough for a lightweight Python worker)
- Deploys directly from your GitHub repo
- Persistent background worker — never spins down
- Simple environment variable management

### Step 1 — Prepare your Google token for the cloud

The OAuth browser flow can't run on a server, so you upload your already-generated token as an environment variable.

In your terminal, run:

```bash
cat token.json
```

Copy the entire output — it's a JSON string. You'll paste this as `GOOGLE_TOKEN_JSON` in Railway in a moment.

### Step 2 — Push your code to GitHub

Your code is already on GitHub. Make sure it's up to date:

```bash
git push
```

> Confirm that `token.json`, `.env`, and `credentials.json` are NOT in your repo (they're in `.gitignore`).

### Step 3 — Create a Railway project

1. Go to [railway.app](https://railway.app) and sign up / log in with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Select your `JOB` repository
4. Railway will detect the `railway.toml` and start building automatically

### Step 4 — Add environment variables

In your Railway project → **Variables** tab, add each of these:

| Variable | Value |
|---|---|
| `GOOGLE_TOKEN_JSON` | The full contents of your `token.json` file |
| `GEMINI_API_KEY` | Your Gemini API key |
| `SPREADSHEET_ID` | Your Google Sheet ID |
| `EMAIL_PROVIDER` | `gmail` |

> Do NOT add `OUTLOOK_CLIENT_ID`, `IMAP_USERNAME`, etc. unless you're using those providers.

### Step 5 — Deploy

Railway will automatically redeploy when you push to GitHub. You can also click **Deploy** manually.

In the **Logs** tab you should see:

```
J*B is running. Monitoring your inbox every 2 hours.
```

### Keeping the token fresh

Google OAuth tokens expire and get refreshed automatically. When running in the cloud, J*B prints the new token value to the logs after a refresh. If you ever see an authentication error:

1. Re-run `python main.py` locally once (it will refresh `token.json`)
2. Copy the new `token.json` contents
3. Update `GOOGLE_TOKEN_JSON` in Railway's Variables tab
4. Railway will redeploy automatically

---

## Security Notes

- `credentials.json`, `token.json`, `outlook_token.json`, and `.env` are all in `.gitignore` and must never be committed to version control.
- The agent never stores or logs the full email body — only the AI-extracted summary is written to the sheet.
