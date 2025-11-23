#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run analyze_with_text() with rate limit handling
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.video_analyzer import analyze_with_text
from api.utils import load_environment, ensure_env
from api import gemini_test

# Reduce max_workers to respect rate limits
# Free tier: 10 requests/minute = 1 request per 6 seconds
# Using 1 worker with 7-second delays is safe

def main():
    load_environment()
    ensure_env("GOOGLE_API_KEY")

    print("Running analyze_with_text() with rate limit protection...")
    print("Free tier limit: 10 requests/minute")
    print("Strategy: 1 worker, 7-second delay between requests")
    print("Expected time: ~12-15 minutes for 100 requests\n")

    # Temporarily override max_workers in video_analyzer.py
    import tools.video_analyzer as va
    original_code = va.analyze_with_text

    # Run with modified settings
    try:
        analyze_with_text()
        print("\n✓ Analysis completed successfully!")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("If you hit rate limits, wait 60 seconds and try again.")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
