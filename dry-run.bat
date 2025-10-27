@echo off
echo Running PC Parts Price Notifier - DRY RUN MODE
echo This will show matching deals without sending notifications
echo.
REM Use local files so GitHub Actions' tracked files don't change on your PC
set "SEEN_FILE=local_seen_posts.txt"
set "LOG_FILE=local_run_log.txt"

python pc_parts_price_notifier.py --dry-run
echo.
echo Dry run complete! Check the output above for matching deals.
echo Local log: %LOG_FILE%
pause