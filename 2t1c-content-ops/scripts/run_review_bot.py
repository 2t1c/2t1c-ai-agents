#!/usr/bin/env python3
"""Launcher for Telegram Review Bot — used by LaunchAgent for 24/7 operation."""
import os
import sys
import signal
import time

# Ensure the project root is in the path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

# Ignore SIGHUP which launchd may send
signal.signal(signal.SIGHUP, signal.SIG_IGN)

# Retry loop in case of transient failures
MAX_RETRIES = 5
for attempt in range(1, MAX_RETRIES + 1):
    try:
        from tools.telegram_review_bot import main
        main()
        break  # Clean exit
    except Exception as e:
        print(f"[run_review_bot] Attempt {attempt}/{MAX_RETRIES} failed: {e}", file=sys.stderr)
        if attempt < MAX_RETRIES:
            time.sleep(10)
        else:
            print("[run_review_bot] Max retries reached, exiting.", file=sys.stderr)
            sys.exit(1)
