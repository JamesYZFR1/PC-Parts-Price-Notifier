@echo off
echo Running PC Parts Price Notifier - TEST MODE
echo.
REM Use local files so GitHub Actions' tracked files don't change on your PC
set "SEEN_FILE=local_seen_posts.txt"
set "LOG_FILE=local_run_log.txt"

python pc_parts_price_notifier.py --test
echo.
echo Test notification sent! Check your Discord/notification channels.
echo Local log: %LOG_FILE%
pause