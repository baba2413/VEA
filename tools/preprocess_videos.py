#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preprocess downloaded videos for experiment:
1. Generate text descriptions (video_to_text)
2. Analyze with text (analyze_with_text)
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.video_analyzer import video_to_text, analyze_with_text
from api.utils import load_environment, ensure_env

def main():
    print("="*60)
    print("Video Preprocessing for Experiment")
    print("="*60)

    # Load environment
    load_environment()
    ensure_env("GOOGLE_API_KEY")

    # Step 1: Generate text descriptions
    print("\nStep 1: Generating text descriptions from videos...")
    print("This may take 20-30 minutes depending on API speed.")
    print("Processing videos in tools/yt_shorts/...")

    try:
        video_to_text(folder_path="yt_shorts")
        print("\n✓ Step 1 completed: Text descriptions generated")
    except Exception as e:
        print(f"\n✗ Step 1 failed: {e}")
        return

    # Step 2: Analyze with text
    print("\n" + "="*60)
    print("Step 2: Analyzing videos with text descriptions...")
    print("This may take 15-20 minutes (5 criteria × 20 videos).")

    try:
        analyze_with_text()
        print("\n✓ Step 2 completed: Analysis results generated")
    except Exception as e:
        print(f"\n✗ Step 2 failed: {e}")
        return

    print("\n" + "="*60)
    print("✓ All preprocessing completed successfully!")
    print("Ready to run experiment_runner.py")
    print("="*60)

if __name__ == "__main__":
    main()
