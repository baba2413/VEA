#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Experiment: Test remaining 13 videos to complete the 18-video dataset
"""

import os
import sys
import json
import time
import statistics
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.gemini_test import feedback_with_llm, feedback_with_video, refresh_all


def run_text_based_feedback(file_name: str, criteria: str, feedback: str) -> Tuple[str, float, bool, str]:
    """
    Run text-based feedback and measure time
    Returns: (result, elapsed_time, success, error_type)
    """
    start_time = time.perf_counter()
    try:
        feedback_with_llm(file_name, criteria, feedback)
        elapsed = time.perf_counter() - start_time
        return "Text-based feedback completed", elapsed, True, None
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        error_str = str(e)
        # Check for rate limit errors
        error_type = "rate_limit" if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower() else "other"
        return error_str, elapsed, False, error_type


def run_video_based_feedback(video_path: str, file_name: str, criteria: str, feedback: str) -> Tuple[str, float, bool, str]:
    """
    Run video-based feedback and measure time
    Returns: (result, elapsed_time, success, error_type)
    """
    start_time = time.perf_counter()
    try:
        feedback_with_video(video_path, file_name, criteria, feedback)
        elapsed = time.perf_counter() - start_time
        return "Video-based feedback completed", elapsed, True, None
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        error_str = str(e)
        # Check for rate limit errors
        error_type = "rate_limit" if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower() else "other"
        return error_str, elapsed, False, error_type


def prepare_test_feedbacks():
    """Prepare test feedback strings for each criteria"""
    return {
        "violence": ["폭력 장면이 너무 자극적입니다", "폭력 수위가 낮아 보입니다"],
        "sexuality": ["선정적인 표현이 과도합니다", "건전한 수준입니다"],
        "horror": ["공포 요소가 강합니다", "깜짝 놀라는 수준입니다"],
        "drugs": ["약물 사용을 미화하고 있습니다", "단순 묘사일 뿐입니다"],
        "language": ["욕설이 많습니다", "언어 표현이 적절합니다"]
    }


def main():
    """Run experiment on remaining 13 videos"""

    print("="*60)
    print("Experiment: Testing Remaining 13 Videos")
    print("="*60)
    print()

    # Load remaining videos list
    with open('remaining_videos.json', 'r', encoding='utf-8') as f:
        remaining_videos = json.load(f)

    print(f"Found {len(remaining_videos)} remaining videos to test")
    print()

    # Configuration
    text_delay = 7
    video_delay = 10
    num_trials = 1  # Just 1 trial for the remaining videos

    # Setup paths
    video_dir = Path(__file__).parent / "yt_shorts"

    test_feedbacks = prepare_test_feedbacks()
    criteria_list = ["violence", "sexuality", "horror", "drugs", "language"]

    all_trials = []

    for trial_num in range(1, num_trials + 1):
        print(f"\n{'='*60}")
        print(f"Trial {trial_num} - Testing {len(remaining_videos)} videos")
        print(f"{'='*60}\n")

        # Refresh data before starting
        refresh_all()

        results = {
            "trial_number": trial_num,
            "timestamp": datetime.now().isoformat(),
            "text_delay": text_delay,
            "video_delay": video_delay,
            "text_based": [],
            "video_based": []
        }

        # Run text-based feedback tests
        print("Running text-based feedback tests...")

        for i, video_file in enumerate(remaining_videos):
            criteria = criteria_list[i % len(criteria_list)]
            feedback = test_feedbacks[criteria][0]

            result, elapsed, success, error_type = run_text_based_feedback(video_file, criteria, feedback)
            results["text_based"].append({
                "video": video_file,
                "criteria": criteria,
                "feedback": feedback,
                "elapsed_time": elapsed,
                "success": success,
                "result": result,
                "error_type": error_type
            })

            if success:
                print(f"  ✓ {video_file[:40]}... ({criteria}): {elapsed:.3f}s")
            else:
                print(f"  ✗ {video_file[:40]}... ({criteria}): {result}")
                if error_type == "rate_limit":
                    print(f"  ⚠️  RATE LIMIT detected! Waiting 30 seconds...")
                    time.sleep(30)

            # Delay between tests
            if i < len(remaining_videos) - 1:
                time.sleep(text_delay)

        # Wait before video-based tests
        print(f"\nWaiting {video_delay} seconds before video-based tests...\n")
        time.sleep(video_delay)

        # Run video-based feedback tests
        print("Running video-based feedback tests...")

        for i, video_file in enumerate(remaining_videos):
            criteria = criteria_list[i % len(criteria_list)]
            feedback = test_feedbacks[criteria][1]
            video_path = str(video_dir / video_file)

            result, elapsed, success, error_type = run_video_based_feedback(video_path, video_file, criteria, feedback)
            results["video_based"].append({
                "video": video_file,
                "criteria": criteria,
                "feedback": feedback,
                "elapsed_time": elapsed,
                "success": success,
                "result": result,
                "error_type": error_type
            })

            if success:
                print(f"  ✓ {video_file[:40]}... ({criteria}): {elapsed:.3f}s")
            else:
                print(f"  ✗ {video_file[:40]}... ({criteria}): {result}")
                if error_type == "rate_limit":
                    print(f"  ⚠️  RATE LIMIT detected! Waiting 30 seconds...")
                    time.sleep(30)

            # Delay between tests
            if i < len(remaining_videos) - 1:
                time.sleep(video_delay)

        all_trials.append(results)

        # Save trial results
        trial_file = Path(__file__).parent / "experiment_results" / f"remaining_trial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(trial_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\nTrial {trial_num} results saved to: {trial_file}")

    # Calculate statistics
    print(f"\n{'='*60}")
    print("Analyzing results...")
    print(f"{'='*60}\n")

    # Collect timing data
    text_times = []
    video_times = []
    text_failures = 0
    video_failures = 0
    text_rate_limits = 0
    video_rate_limits = 0

    for trial in all_trials:
        for test in trial["text_based"]:
            if test["success"]:
                text_times.append(test["elapsed_time"])
            else:
                text_failures += 1
                if test["error_type"] == "rate_limit":
                    text_rate_limits += 1

        for test in trial["video_based"]:
            if test["success"]:
                video_times.append(test["elapsed_time"])
            else:
                video_failures += 1
                if test["error_type"] == "rate_limit":
                    video_rate_limits += 1

    # Calculate stats
    analysis = {
        "text_based": {
            "count": len(text_times),
            "failures": text_failures,
            "rate_limit_errors": text_rate_limits,
            "mean": statistics.mean(text_times) if text_times else 0,
            "median": statistics.median(text_times) if text_times else 0,
            "stdev": statistics.stdev(text_times) if len(text_times) > 1 else 0,
            "min": min(text_times) if text_times else 0,
            "max": max(text_times) if text_times else 0,
            "total": sum(text_times)
        },
        "video_based": {
            "count": len(video_times),
            "failures": video_failures,
            "rate_limit_errors": video_rate_limits,
            "mean": statistics.mean(video_times) if video_times else 0,
            "median": statistics.median(video_times) if video_times else 0,
            "stdev": statistics.stdev(video_times) if len(video_times) > 1 else 0,
            "min": min(video_times) if video_times else 0,
            "max": max(video_times) if video_times else 0,
            "total": sum(video_times)
        },
        "comparison": {}
    }

    # Calculate comparison
    if text_times and video_times:
        text_mean = analysis["text_based"]["mean"]
        video_mean = analysis["video_based"]["mean"]

        if text_mean < video_mean:
            analysis["comparison"]["speedup_ratio"] = video_mean / text_mean
            analysis["comparison"]["time_difference"] = video_mean - text_mean
            analysis["comparison"]["faster_method"] = "text_based"
        else:
            analysis["comparison"]["speedup_ratio"] = text_mean / video_mean
            analysis["comparison"]["time_difference"] = text_mean - video_mean
            analysis["comparison"]["faster_method"] = "video_based"

    # Save final results
    experiment_data = {
        "experiment_id": f"remaining_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "configuration": {
            "num_trials": num_trials,
            "num_tests_per_trial": len(remaining_videos),
            "text_delay": text_delay,
            "video_delay": video_delay
        },
        "analysis": analysis,
        "all_trials": all_trials
    }

    results_file = Path(__file__).parent / "experiment_results" / f"experiment_remaining_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(experiment_data, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n{'='*60}")
    print("EXPERIMENT RESULTS SUMMARY - REMAINING 13 VIDEOS")
    print(f"{'='*60}\n")

    print(f"Text-based approach:")
    print(f"  Tests completed: {analysis['text_based']['count']}")
    print(f"  Failures: {analysis['text_based']['failures']}")
    print(f"  Rate limit errors: {analysis['text_based']['rate_limit_errors']}")
    print(f"  Mean time: {analysis['text_based']['mean']:.3f}s")
    print(f"  Median time: {analysis['text_based']['median']:.3f}s")
    print(f"  Std dev: {analysis['text_based']['stdev']:.3f}s")
    print(f"  Range: {analysis['text_based']['min']:.3f}s - {analysis['text_based']['max']:.3f}s")
    print()

    print(f"Video-based approach:")
    print(f"  Tests completed: {analysis['video_based']['count']}")
    print(f"  Failures: {analysis['video_based']['failures']}")
    print(f"  Rate limit errors: {analysis['video_based']['rate_limit_errors']}")
    print(f"  Mean time: {analysis['video_based']['mean']:.3f}s")
    print(f"  Median time: {analysis['video_based']['median']:.3f}s")
    print(f"  Std dev: {analysis['video_based']['stdev']:.3f}s")
    print(f"  Range: {analysis['video_based']['min']:.3f}s - {analysis['video_based']['max']:.3f}s")
    print()

    if analysis["comparison"]:
        print(f"Comparison:")
        print(f"  Speedup ratio: {analysis['comparison']['speedup_ratio']:.2f}x")
        print(f"  Time difference: {analysis['comparison']['time_difference']:.3f}s")
        print(f"  Faster method: {analysis['comparison']['faster_method']}")
        print()

    print(f"{'='*60}")
    print(f"Final results saved to: {results_file}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
