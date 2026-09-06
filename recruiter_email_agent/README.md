# Recruiter Cold Email Agent

A deterministic, safety-first tool for sending personalized cold emails to
recruiters based on job postings you find manually (e.g. on LinkedIn).

**What it is:** placeholder substitution into a fixed template, a preview/
approval step, Gmail sending via OAuth, SQLite tracking, rate limiting, and
a daily send cap.

**What it is not:** there is no LLM in the sending path, and it does **not**
scrape LinkedIn or bypass any platform's login/CAPTCHA protections. You
supply recruiter/job details yourself (typed in, or via CSV/Excel).

```
CSV → Validate → Generate → Preview → Approve → Send → Track → Log
```

---

## 1. Create the virtual environment

```bash
cd recruiter_email_agent
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Configure Gmail OAuth

The app uses the Gmail API with OAuth 2.0 — no password is ever stored.

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create
   (or select) a project.
2. Enable the **Gmail API** for that project.
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth
   client ID**, choose **Desktop app**, and create it.
4. Download the JSON file and save it as `credentials.json` in the project
   root (or point `GMAIL_CREDENTIALS_PATH` at it — see step 7).
5. The **first time** you send an email, a browser window will open asking
   you to sign in and authorize the app. After that, a `token.json` file is
   created automatically and reused (refreshed silently) on future runs.

Both `credentials.json` and `token.json` are already listed in
`.gitignore` — never commit them.

## 4. Where to put the resume

Put your resume anywhere on disk and point `RESUME_PATH` at it (step 7).
The same file is attached to every email that is actually sent. If the
file doesn't exist at send time, the app stops and sends nothing:

```
Resume not found.
Emails will not be sent.
```

## 5. How to configure the email template

The master template lives at `config/email_template.txt`. Edit it freely —
the app will not paraphrase or rewrite it. Only these placeholders are
replaced automatically:

* `{HR_NAME}` — from the recruiter row
* `{COMPANY_NAME}` — from the recruiter row
* `{JOB_ROLE}` — from the recruiter row
* `{YOUR_NAME}` — from `SENDER_NAME` in your `.env`

The first line of the template must be `Subject: ...`; everything after
the first blank line is the email body. Everything else is copied through
unchanged.

## 6. How to create `recruiters.csv`

Columns (case-insensitive; common aliases like `role`/`position` for
`job_role`, or `name` for `hr_name`, are also accepted):

```csv
hr_name,company,job_role,email,linkedin_url
Priya Sharma,Google,Data Scientist,priya@google.com,https://www.linkedin.com/jobs/...
Rahul Kumar,Microsoft,ML Engineer,rahul@microsoft.com,https://www.linkedin.com/jobs/...
```

`linkedin_url` is optional and stored for your own record-keeping only. An
`.xlsx` file with the same columns works too (`--input recruiters.xlsx`).
A sample file is at `data/recruiters.csv`.

## 7. Configure `.env`

```bash
cp .env.example .env
```

Then edit `.env`:

```env
SENDER_NAME=Your Name
EMAIL_PROVIDER=gmail
RESUME_PATH=/absolute/path/to/your_resume.pdf
AUTO_SEND=false
DAILY_EMAIL_LIMIT=30
MIN_DELAY_SECONDS=30
MAX_DELAY_SECONDS=90
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
```

`AUTO_SEND=false` (the default) means you'll be shown a preview and asked
`Send this email? [Y/N]` before each send. Set it to `true` only once
you're confident in the template and list — or pass `--yes` on a single run.

## 8. How to run preview mode

Generates and prints every email — no network calls, nothing sent:

```bash
python main.py --input data/recruiters.csv --preview
```

## 9. How to run dry-run mode

Runs the full pipeline (validation, duplicate check, generation) and
records a `SKIPPED` row per recruiter, but **never** calls the Gmail
provider:

```bash
python main.py --input data/recruiters.csv --dry-run
```

## 10. How to send emails

```bash
python main.py --input data/recruiters.csv
```

You'll be asked to approve each email individually (unless
`AUTO_SEND=true` or you pass `--yes`). Between successful sends the app
waits a random delay (`MIN_DELAY_SECONDS`–`MAX_DELAY_SECONDS`) and stops
automatically once `DAILY_EMAIL_LIMIT` is reached for the day.

Sample output:

```
Processing 3 recruiters...

[1/3] Priya Sharma — Google — Data Scientist
✓ Email sent

[2/3] Rahul Kumar — Microsoft — ML Engineer
SKIPPED — Already contacted

[3/3] Ankit Singh — Amazon — AI Engineer
✗ FAILED — Invalid email address

--------------------------------
SUMMARY
--------------------------------
Total: 3
Sent: 1
Skipped: 1
Failed: 1
--------------------------------
```

## 11. How to view history / status

```bash
python main.py --status     # counts by status, sent-today count
python main.py --history    # most recent contact attempts
```

---

## Web UI (optional, alternative to the CLI)

If you'd rather enter recruiters and send from a browser instead of a
CSV + terminal, run:

```bash
python webapp.py
```

Then open **http://127.0.0.1:5000**. It's the same pipeline as the CLI —
just a browser front-end over the same `agent/`, `database/`, and
`providers/` modules:

* **Add Recruiter** form — writes each entry as a new row in the CSV at
  `RECRUITERS_CSV_PATH` (defaults to `data/recruiters.csv`; same file the
  CLI's `--input` flag reads).
* **Recruiter List** table — shows every row in that CSV with a live
  status badge (`NEW` / `SENT` / `FAILED` / `SKIPPED`) pulled from the
  same SQLite tracking database the CLI uses, so CLI and UI runs stay in
  sync automatically.
* **Preview** — renders the exact subject/body that would be sent, with
  warnings if the recruiter was already contacted or the resume file is
  missing.
* **Confirm & Send** — this button click *is* the explicit approval step
  (same one the CLI's `[Y/N]` prompt asks for); it then runs the same
  validate → duplicate-check → daily-limit-check → send → track → log
  sequence, including Gmail OAuth on first use.
* **Delete** — removes a row from the CSV (does not affect DB history).

Configuration (optional, in `.env`):

```env
RECRUITERS_CSV_PATH=data/recruiters.csv
WEB_UI_HOST=127.0.0.1
WEB_UI_PORT=5000
```

The UI is intended for local, single-user use on your own machine —
it isn't hardened for exposing on a network or the internet.

---

## Project structure

```
recruiter_email_agent/
├── main.py                  # CLI entrypoint
├── webapp.py                 # Optional local web UI (Flask)
├── templates/                # UI HTML (index, preview)
├── static/                   # UI stylesheet
├── config/
│   ├── settings.py          # env-driven Settings object
│   └── email_template.txt   # master template (edit this, not the code)
├── agent/
│   ├── email_generator.py   # deterministic placeholder substitution
│   ├── validator.py         # field + email-format + placeholder checks
│   └── processor.py         # orchestrates validate→generate→preview→send→track
├── providers/
│   ├── base.py               # EmailProvider interface
│   └── gmail.py               # Gmail API + OAuth 2.0 implementation
├── database/
│   ├── db.py                 # SQLite access (tracking, dedup, stats)
│   └── models.py              # RecruiterRecord / ContactStatus
├── input/
│   ├── csv_reader.py
│   ├── csv_writer.py         # used by the web UI to append/delete rows
│   └── excel_reader.py
├── utils/
│   ├── logger.py
│   └── rate_limiter.py
├── data/
│   └── recruiters.csv        # sample input
├── tests/
├── .env.example
├── .gitignore
└── requirements.txt
```

## Running the tests

```bash
pip install -r requirements.txt   # includes pytest
pytest tests/ -v
```

Tests cover: placeholder replacement, unresolved-placeholder detection,
email-format validation, duplicate detection (SQLite), daily-limit
enforcement, dry-run (never calls the provider), and missing-attachment
handling.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `Gmail OAuth client secret not found at: credentials.json` | Download the OAuth client JSON from Google Cloud Console and place it at the path in `GMAIL_CREDENTIALS_PATH`. |
| Browser doesn't open for authorization | Make sure you're running the command in an environment with a browser available; for headless servers, run the first authorization locally, then copy the resulting `token.json` over. |
| `Resume not found. Emails will not be sent.` | Check `RESUME_PATH` in `.env` — it must be an absolute (or correctly relative) path to a file that exists. |
| `Missing recruiter email for X. Email was NOT sent.` | The CSV/Excel row is missing an email value, or the header wasn't recognized — check column names against §6 above. |
| `SKIPPED — Already contacted: ...` | That email address already has a `SENT` row in the database (`database/recruiter_agent.db`). This is intentional dedup; delete the row manually if you really want to re-send. |
| `Daily email limit reached.` | You've hit `DAILY_EMAIL_LIMIT` for today (UTC-day boundary). Wait until tomorrow or raise the limit in `.env`. |
| `ModuleNotFoundError: No module named 'google...'` | Run `pip install -r requirements.txt` inside your activated virtual environment. |
| Emails sending too fast / risk of spam flags | Increase `MIN_DELAY_SECONDS` / `MAX_DELAY_SECONDS`, and keep `DAILY_EMAIL_LIMIT` conservative (Gmail's own daily sending caps also apply). |
| Want to test without any real sending | Use `--preview` (no DB writes for sent emails, no network) or `--dry-run` (writes SKIPPED rows, no network). |

## Safety notes

* Defaults to `AUTO_SEND=false` — every send needs a `[Y/N]` confirmation
  unless you explicitly opt in.
* Never sends to an invalid email address or to an address already marked
  `SENT` in the database.
* Does not scrape LinkedIn, bypass CAPTCHAs, or automate login flows —
  job/recruiter data is supplied by you, manually or via CSV/Excel.
* No secrets are logged; `credentials.json`, `token.json`, and `.env` are
  git-ignored.
