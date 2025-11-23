#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze videos with rate limit protection (sequential processing)
"""

import json
import re
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.gemini_test import analyze_with_gemini, make_prompt
from api.utils import load_environment, ensure_env

def main():
    load_environment()
    ensure_env("GOOGLE_API_KEY")

    criteria_list = ["violence", "sexuality", "horror", "drugs", "language"]

    # Load files
    script_dir = Path(__file__).parent
    video_text_path = script_dir / "video_text.json"
    analysis_results_path = script_dir.parent / "api" / "analysis_results.json"

    with open(video_text_path, "r", encoding="utf-8") as f:
        video_text = json.load(f)

    try:
        with open(analysis_results_path, "r", encoding="utf-8") as f:
            analysis_results = json.load(f)
    except FileNotFoundError:
        analysis_results = {}

    # Find videos that need analysis
    to_process = [v for v in video_text.keys() if v not in analysis_results]

    print(f"Videos to analyze: {len(to_process)}")
    print(f"Total API calls needed: {len(to_process) * len(criteria_list)}")
    print(f"Rate limit: 10 requests/minute")
    print(f"Strategy: 1 request every 7 seconds")
    print(f"Estimated time: ~{len(to_process) * len(criteria_list) * 7 // 60} minutes\n")

    if not to_process:
        print("All videos already analyzed!")
        return

    request_count = 0
    start_time = time.time()

    for video in to_process:
        print(f"\nAnalyzing: {video[:60]}...")
        analysis_results[video] = {"ox": {}, "details": {}}

        for criteria in criteria_list:
            # Build prompt
            msg = make_prompt(file_name=video, criteria=criteria)

            # Call API
            try:
                result = analyze_with_gemini(prompt=msg)
                request_count += 1

                # Parse result
                m1 = re.search(rf"{criteria}\s*:\s*(0|1)", result)
                ox_value = int(m1.group(1)) if m1 else -1

                m2 = re.search(r"근거\s*:\s*(.*)", result, re.DOTALL)
                detail = m2.group(1).strip() if m2 else "error"

                analysis_results[video]["ox"][criteria] = ox_value
                analysis_results[video]["details"][criteria] = detail

                print(f"  ✓ {criteria}: {ox_value}")

                # Save incrementally
                with open(analysis_results_path, "w", encoding="utf-8") as f:
                    json.dump(analysis_results, f, ensure_ascii=False, indent=2)

                # Rate limit: wait 7 seconds between requests
                if request_count % 10 == 0:
                    elapsed = time.time() - start_time
                    print(f"\n  [{request_count} requests in {elapsed:.1f}s] Waiting 10s for rate limit...")
                    time.sleep(10)
                    start_time = time.time()
                else:
                    time.sleep(7)

            except Exception as e:
                print(f"  ✗ {criteria}: Error - {e}")
                if "429" in str(e) or "quota" in str(e).lower():
                    print(f"  Rate limit hit! Waiting 60 seconds...")
                    time.sleep(60)
                    # Retry once
                    try:
                        result = analyze_with_gemini(prompt=msg)
                        m1 = re.search(rf"{criteria}\s*:\s*(0|1)", result)
                        ox_value = int(m1.group(1)) if m1 else -1
                        m2 = re.search(r"근거\s*:\s*(.*)", result, re.DOTALL)
                        detail = m2.group(1).strip() if m2 else "error"
                        analysis_results[video]["ox"][criteria] = ox_value
                        analysis_results[video]["details"][criteria] = detail
                        print(f"  ✓ {criteria}: {ox_value} (retry successful)")
                    except Exception as e2:
                        print(f"  ✗ Retry failed: {e2}")
                        analysis_results[video]["ox"][criteria] = -1
                        analysis_results[video]["details"][criteria] = f"Error: {str(e2)}"

    print(f"\n{'='*60}")
    print(f"✓ Analysis complete!")
    print(f"Total videos processed: {len(to_process)}")
    print(f"Total API calls: {request_count}")
    print(f"Results saved to: {analysis_results_path}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
