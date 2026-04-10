#!/bin/bash
# Launcher for Telegram Review Bot — called by LaunchAgent
echo "[$(date)] Review bot starting..." >&2
cd "/Users/toantruong/Desktop/AI Agents/2t1c-content-ops" || { echo "cd failed" >&2; exit 1; }
export PYTHONPATH="/Users/toantruong/Desktop/AI Agents/2t1c-content-ops"
export PYTHONUNBUFFERED=1
echo "[$(date)] Running python3..." >&2
exec /usr/bin/python3 -u scripts/run_review_bot.py 2>&1
