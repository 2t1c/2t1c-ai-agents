#!/usr/bin/env python3
"""Launcher for CEO Telegram bot — used by LaunchAgent for 24/7 operation."""
import os
import sys

# Ensure the project root is in the path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from agents.ceo.telegram_bot import main
main()
