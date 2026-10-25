# Kite Token Updater

Automatically logs in to Zerodha Kite every weekday morning and saves a fresh `access_token` to `keys.txt`, so your trading scripts always have a valid token.

Kite access tokens expire daily, and the official login needs a browser, password and TOTP. This script does that login for you in a headless browser.

## How it works

1. Between 9:00 and 9:15 AM IST on weekdays, the script wakes up.
2. It starts a tiny local web server on `localhost:8000`.
3. It opens the Kite login page in a headless Chromium browser (Playwright), then fills in your user ID, password and a generated TOTP code.
4. After a successful login, Zerodha redirects the browser to `http://localhost:8000/?request_token=...`. The local server catches that redirect and reads the `request_token`.
5. The script exchanges the `request_token` for an `access_token` using the KiteConnect API.
6. Both tokens are written back into `keys.txt`.

The rest of the day it just sleeps and checks the clock. It is meant to run forever under a process manager such as PM2.

## Requirements

- Python 3.9+
- A Zerodha account with the **Kite Connect** API subscription
- External TOTP (authenticator app) enabled on your Kite account

Install the packages:

```bash
pip install pytz pyotp requests kiteconnect playwright
playwright install chromium
```

## Setup

### 1. Create a Kite Connect app

At [developers.kite.trade](https://developers.kite.trade), create an app and set its **Redirect URL** to exactly:

```
http://localhost:8000
```

This is how the script receives the `request_token`. If it doesn't match, login will time out.

### 2. Fill in `keys.txt`

Copy the sample file and fill in your values. One `key=value` per line, no spaces or quotes:

```
api_key=
api_secret=
kite_username=
kite_password=
totp_secret=
```

| Field | Where to get it |
|---|---|
| `api_key` / `api_secret` | Your app page on developers.kite.trade |
| `kite_username` | Your Zerodha user ID (e.g. `AB1234`) |
| `kite_password` | Your Kite login password |
| `totp_secret` | The secret key (text) shown when you enable external TOTP in Kite. It is **not** the 6-digit code. |

The script adds two more lines itself after each run: `request_token` and `access_token`. Your other scripts can read `access_token` from this file.

### 3. Change the hardcoded paths

The script has absolute paths from the author's machine. Search for `/Users/apple/` and replace them with your own:

- `sys.path.append(...)` near the top
- the path to `keys.txt` (it appears in `fetch_request_token`, `fetch_user_credentials` and `update_access_token`)

Tip: define the path once as a constant at the top of the file and reuse it.

### 4. Run it

Run once to test (you can temporarily call `fetch_request_token()` and `update_access_token()` directly, outside the time window):

```bash
python update_kite_tokens.py
```

Run continuously with PM2:

```bash
pm2 start update_kite_tokens.py --interpreter python3 --name kite-token-updater
pm2 save
```

## Schedule

All times are IST, weekdays only (Mon-Fri):

| Time | What happens |
|---|---|
| 08:00 - 08:45 | Sleeps 15 minutes at a time |
| 08:45 - 09:00 | Sleeps 1 minute at a time |
| 09:00 - 09:15 | Logs in, updates tokens, then sleeps 16 minutes |
| Any other time | Sleeps 1 hour at a time |

## Troubleshooting

- **"Timed out waiting for request token"**: login didn't finish within 30 seconds. Check your password, `totp_secret`, and that the redirect URL is `http://localhost:8000`.
- **Port 8000 already in use**: something else is using it. Stop it, or change the port in both the script and your Kite app's redirect URL.
- **Invalid TOTP code**: your computer clock may be off. The script corrects for this by comparing against Google's server time, but it needs internet access for that.
- **Login button or fields not found**: Zerodha may have changed their login page. The script finds fields by their labels ("Phone number or User ID", "Password", "External TOTP", "Continue"), so update those if the page changes.

## Security warning

`keys.txt` holds your password, TOTP secret and API secret in plain text. Anyone who gets that file can access your trading account.

```
keys.txt
```

- Keep the file readable only by you: `chmod 600 keys.txt`
- Storing the password and the TOTP secret together weakens two-factor protection. Only run this on a machine you trust.

## Disclaimer

This is a personal automation tool, provided as is, with no warranty. Check Zerodha's terms before automating logins. You are responsible for your account and any trades placed using these tokens. This is not financial advice.