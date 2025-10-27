# PC Parts Price Notifier

This script monitors /r/bapcsalescanada RSS feed and sends notifications for PC parts deals based on configurable price thresholds.

## Quick Start Batch Files

Double-click these files for easy testing:
- **`test.bat`** - Sends a test notification to verify your Discord webhook is working
- **`dry-run.bat`** - Shows what deals would be detected without sending notifications

## Current Filters

The script will notify you for:

1. **CPUs under $500** - Detects posts with `[CPU]` tags, known CPU models, or containing words like 'processor' or 'cpu'
2. **CPU Bundles under $600** - Detects posts with `[CPU Bundle]` tags or containing "cpu bundle"
3. **GPUs under $800** - Detects posts with `[GPU]` tags
4. **Monitors under $1000** - Detects posts containing the word "monitor"
5. **Specific CPU models** - Always alerts for: 5800X3D, 7600X3D, 7800X3D (if price is under $500)

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

## How It Works

1. Fetches RSS feed from /r/bapcsalescanada
2. Extracts prices from post titles (prefers "=$123" format, falls back to last $amount)
3. Checks each post against the filters above
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

Notes:
- GitHub’s cron is best-effort and roughly every 5 minutes at minimum.
- If you prefer not to commit state, switch to a Gist or S3/DB storage and update the script accordingly.

## Other low-cost/low-power options

- Raspberry Pi / low-power SBC: install Python and use `cron` to call the script.
- Android phone + Termux: run a scheduled job with `cronie` or Tasker.
- Cloud free tiers: AWS Lambda + EventBridge (schedule) with S3 for `seen_posts.txt`, or Cloudflare Workers + KV (requires a JS port).