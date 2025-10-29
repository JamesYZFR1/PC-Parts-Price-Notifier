# PC Parts Price Notifier

This script monitors:

- /r/bapcsalescanada RSS feed for price-based PC parts deals
- /r/CanadianHardwareSwap RSS feed for high-end GPU keyword matches (regardless of price)

## Quick Start Batch Files

Double-click these files for easy testing:
- **`test.bat`** - Sends a test notification to verify your Discord webhook is working
- **`dry-run.bat`** - Shows what deals would be detected without sending notifications

## Current Filters

The script will notify you for:

1. **CPUs under $500** - Detects posts with `[CPU]` tags, known CPU models, or containing words like 'processor' or 'cpu'
2. **CPU Bundles under $600** - Detects posts with `[CPU Bundle]` tags or containing "cpu bundle"
3. **GPUs under $800** - Detects posts with `[GPU]` tags (bapcsalescanada)
4. **Monitors under $1000** - Detects posts containing the word "monitor"
5. **Specific CPU models** - Always alerts for: 5800X3D, 7600X3D, 7800X3D (if price is under $500)

Additionally, the notifier checks the r/CanadianHardwareSwap feed and alerts on titles containing any of these GPU models (case/spacing variations supported):

- RTX 5090, 5090
- RTX 4090, 4090
- RTX 4080 SUPER, 4080 SUPER, 4080
- RTX 5070 Ti, 5070 Ti
- RX 7900 XTX, 7900 XTX
- RX 7900 XT, 7900 XT
- RX 9070 XT, 9070 XT, RX 9070

## Configuration

Edit the top of `pc_parts_price_notifier.py` to adjust thresholds:

```python
# Price thresholds
GPU_PRICE_LIMIT = 800
MONITOR_PRICE_LIMIT = 1000
CPU_PRICE_LIMIT = 500          # notify for CPUs under this price
CPU_BUNDLE_PRICE_LIMIT = 600   # notify for [CPU Bundle] under this price

# Target CPU models (checked against CPU_PRICE_LIMIT)
CPU_MODELS = ["5800x3d", "7600x3d", "7800x3d"]
```

## Command Line Usage

```powershell
# Normal run (sends notifications)
python pc_parts_price_notifier.py

# Test notification
python pc_parts_price_notifier.py --test

# Dry run (shows matches without notifications)
python pc_parts_price_notifier.py --dry-run
```

### Environment variables (optional)

You can override configuration via env vars instead of editing the script:

- `APPRISE_URLS` – Comma‑separated Apprise URLs (e.g., your Discord webhook)
- `ROLE_MENTION` – Optional Discord role mention like `<@&123456789012345678>`
- `FEED_URL` – RSS URL to read
- `CHS_FEED_URL` – RSS URL for r/CanadianHardwareSwap (defaults to `https://old.reddit.com/r/CanadianHardwareSwap/.rss`)
- `SEEN_FILE` – Path to file for storing alerted post IDs
- `LOG_FILE` – Path to the run log file
- `TIMEZONE` – IANA timezone like `America/Toronto` or `UTC` (affects timestamps in logs)

PowerShell example for a one‑off session:

```powershell
$env:APPRISE_URLS = "https://discord.com/api/webhooks/..."
$env:TIMEZONE = "America/Toronto"
python .\pc_parts_price_notifier.py --dry-run
```

## How It Works

1. Fetches RSS feed from /r/bapcsalescanada and /r/CanadianHardwareSwap
2. Extracts prices from post titles (prefers "=$123" format, falls back to last $amount)
3. Checks each bapcsalescanada post against price filters, and each CanadianHardwareSwap post against the GPU keyword list
4. Skips posts it has already alerted for (stored in `seen_posts.txt`)
5. Sends notifications via configured Apprise URLs (Discord webhook, etc.)
6. Logs activity to `run_log.txt`

## Run it 24/7 for free (GitHub Actions)

You can run this checker on a schedule in the cloud using GitHub Actions. It costs $0 for public repos and has generous minutes for private repos. The workflow is included at `.github/workflows/deal-notifier.yml` and runs every 5 minutes.

Setup:
- In your repository settings, add secrets:
	- `APPRISE_URLS` – comma-separated Apprise URLs (e.g., your Discord webhook)
	- `ROLE_MENTION` – optional Discord role mention like `<@&123456789012345678>`
- Push this repo to GitHub. The workflow will run automatically on schedule and can be triggered manually via "Run workflow".

State and logs:
- The workflow commits updates to `seen_posts.txt` back to the repository so the bot won’t re-alert on the same posts.
- The local `run_log.txt` on your PC will NOT update when the workflow runs in the cloud. Instead, each run uploads the workflow's `run_log.txt` as a downloadable artifact named `run_log` (kept for 14 days). Open a workflow run → Artifacts to download.

### Manually trigger test or dry-run from Actions

The workflow supports a Run mode input when you click "Run workflow":

- normal: runs on schedule or manual trigger and sends real alerts
- test: runs `--test` to send a single test notification (useful to verify your webhook and role mention)
- dry-run: runs `--dry-run` to list matches without sending notifications

Note on secrets visibility: GitHub hides secret values. When you edit the `APPRISE_URLS` secret it will appear empty in the UI—that’s normal. Paste a new value to rotate/replace it; you cannot view the old value.

## Avoid local Git conflicts

When you run the script locally, it may update `seen_posts.txt` and `run_log.txt`. Since the GitHub Actions workflow also updates `seen_posts.txt`, this can cause push/pull conflicts.

To avoid that, the provided batch files set environment variables so local runs use separate files:

- `SEEN_FILE=local_seen_posts.txt`
- `LOG_FILE=local_run_log.txt`

These local files are ignored by Git (see `.gitignore`), so your local testing won’t conflict with the cloud workflow’s tracked files.

Notes:
- GitHub’s cron is best-effort and roughly every 5 minutes at minimum.
- If you prefer not to commit state, switch to a Gist or S3/DB storage and update the script accordingly.

## Other low-cost/low-power options

- Raspberry Pi / low-power SBC: install Python and use `cron` to call the script.
- Android phone + Termux: run a scheduled job with `cronie` or Tasker.
- Cloud free tiers: AWS Lambda + EventBridge (schedule) with S3 for `seen_posts.txt`, or Cloudflare Workers + KV (requires a JS port).