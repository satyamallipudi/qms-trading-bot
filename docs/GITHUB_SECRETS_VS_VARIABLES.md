# GitHub Secrets vs Variables - Quick Reference

## The Difference

**Secrets** 🔒
- Encrypted and hidden (values are masked in logs)
- Use for: API keys, passwords, tokens, sensitive data
- Access with: `${{ secrets.NAME }}`

**Variables** 📝
- Plain text (visible in logs, but not in UI)
- Use for: Configuration values, non-sensitive settings
- Access with: `${{ vars.NAME }}`

## What to Use Where

### Use **Secrets** for:
- `LEADERBOARD_API_TOKEN` - Your API token
- `ALPACA_API_KEY` - Your API key
- `ALPACA_API_SECRET` - Your API secret
- `SMTP_PASSWORD` - Email password
- `SMTP_USERNAME` - Email username (if sensitive)
- `EMAIL_RECIPIENT` - Email address (privacy)
- `SMTP_FROM_EMAIL` - From email (if sensitive)
- `FIREBASE_PROJECT_ID` - Firebase project ID
- `FIREBASE_CREDENTIALS_JSON` - Entire Firebase service account JSON file content

### Use **Variables** for:
- `BROKER_TYPE` - `alpaca`, `robinhood`, or `webull`
- `ALPACA_BASE_URL` - `https://paper-api.alpaca.markets`
- `INITIAL_CAPITAL` - `10000.0`
- `EMAIL_ENABLED` - `true` or `false`
- `EMAIL_PROVIDER` - `smtp`, `sendgrid`, or `ses`
- `SMTP_HOST` - `smtp.gmail.com`
- `SMTP_PORT` - `587`
- `LEADERBOARD_API_URL` - Your API endpoint URL

## How to Add Them

### Adding a Secret:
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **"Secrets"** tab
3. Click **"New repository secret"**
4. Enter name and value
5. Click **"Add secret"**

### Adding a Variable:
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **"Variables"** tab
3. Click **"New repository variable"**
4. Enter name and value
5. Click **"Add variable"**

## Quick Setup Checklist

### Required Secrets 🔒
- [ ] `LEADERBOARD_API_TOKEN`
- [ ] `ALPACA_API_KEY`
- [ ] `ALPACA_API_SECRET`

### Required Variables 📝
- [ ] `LEADERBOARD_API_URL`
- [ ] `BROKER_TYPE` (set to `alpaca`, `robinhood`, or `webull`)
- [ ] `ALPACA_BASE_URL` (set to `https://paper-api.alpaca.markets`)
- [ ] `INITIAL_CAPITAL` (set to `10000.0`)

### Optional Email Secrets 🔒
- [ ] `EMAIL_RECIPIENT`
- [ ] `SMTP_USERNAME`
- [ ] `SMTP_PASSWORD`
- [ ] `SMTP_FROM_EMAIL`

### Optional Email Variables 📝
- [ ] `EMAIL_ENABLED` (set to `true` or `false`)
- [ ] `EMAIL_PROVIDER` (set to `smtp`)
- [ ] `SMTP_HOST` (set to `smtp.gmail.com`)
- [ ] `SMTP_PORT` (set to `587`)

### Optional Persistence Secrets 🔒
- [ ] `FIREBASE_PROJECT_ID` - Your Firebase project ID
- [ ] `FIREBASE_CREDENTIALS_JSON` - Entire Firebase service account JSON content

### Optional Persistence Variables 📝
- [ ] `PERSISTENCE_ENABLED` (set to `true` or `false`, auto-enables if credentials are set)

## Common Issues

### ❌ "Variable is empty" error

**Problem:** Variable or secret is not set or has wrong name

**Solution:**
1. Check Settings → Secrets and variables → Actions
2. Verify the name matches exactly (case-sensitive!)
3. Make sure you're using the right type (Secret vs Variable)

### ❌ "Invalid broker type" error

**Problem:** `BROKER_TYPE` is empty or wrong value

**Solution:**
1. Add `BROKER_TYPE` as a **Variable** (not Secret)
2. Set value to exactly `alpaca`, `robinhood`, or `webull` (lowercase)

### ❌ Values showing as empty in logs

**Problem:** Secrets are masked (this is normal!)
- Secrets show as `***` in logs (this is correct)
- Variables show their actual values

## Current Workflow Configuration

The workflow file (`.github/workflows/trading-bot.yml`) is configured to use:
- **Variables** for: `BROKER_TYPE`, `ALPACA_BASE_URL`, `INITIAL_CAPITAL`, `EMAIL_ENABLED`, `EMAIL_PROVIDER`, `SMTP_HOST`, `SMTP_PORT`, `PERSISTENCE_ENABLED`
- **Secrets** for: All API keys, tokens, passwords, email addresses, and Firebase credentials

Make sure you add each value to the correct type!

## Firebase Persistence Setup

For Firebase persistence, you need:

1. **Create Firebase project** and Firestore database (see README)
2. **Download service account JSON** from Firebase Console
3. **Add as secrets:**
   - `FIREBASE_PROJECT_ID` = Your project ID (e.g., `qmsf-e541d`)
   - `FIREBASE_CREDENTIALS_JSON` = Entire JSON file content (copy/paste all content)
4. **Add as variable (optional):**
   - `PERSISTENCE_ENABLED` = `true` (or leave unset - auto-enables if credentials are present)

**⚠️ Important:** Never commit the Firebase JSON file to git. Always use `FIREBASE_CREDENTIALS_JSON` secret for GitHub Actions.
