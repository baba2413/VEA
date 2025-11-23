#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Experiment: Compare feedback generation time between text-based and video-based approaches
"""

import os
import sys
import json
import time
import statistics
import argparse
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


def prepare_test_feedbacks() -> Dict[str, List[str]]:
    """
    Prepare sample feedback messages for each criteria
    """
    return {
        "violence": [
            "폭력 장면이 너무 자극적입니다",
            "폭력 수위가 낮아 보입니다",
        ],
        "sexuality": [
            "선정적인 표현이 과도합니다",
            "건전한 수준입니다",
        ],
        "horror": [
            "공포 요소가 강합니다",
            "깜짝 놀라는 수준입니다",
        ],
        "drugs": [
            "약물 사용을 미화하고 있습니다",
            "단순 묘사일 뿐입니다",
        ],
        "language": [
            "욕설이 많습니다",
            "언어 표현이 적절합니다",
        ]
    }


def run_single_trial(video_files: List[str], video_dir: Path, trial_num: int, num_tests: int = 5,
                     text_delay: int = 3, video_delay: int = 5) -> Dict:
    """
    Run a single trial of the experiment

    Args:
        video_files: List of video filenames
        video_dir: Directory containing videos
        trial_num: Trial number
        num_tests: Number of videos to test
        text_delay: Delay between text-based tests (seconds)
        video_delay: Delay between video-based tests (seconds)
    """
    print(f"\n{'='*60}")
    print(f"Trial {trial_num}")
    print(f"{'='*60}\n")

    # Refresh data before starting
    refresh_all()

    test_feedbacks = prepare_test_feedbacks()
    criteria_list = ["violence", "sexuality", "horror", "drugs", "language"]

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
    rate_limit_hit = False

    for i, video_file in enumerate(video_files[:num_tests]):
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
                rate_limit_hit = True
                print(f"  ⚠️  RATE LIMIT detected! Waiting 30 seconds...")
                time.sleep(30)

        # Delay between tests
        if i < num_tests - 1:
            time.sleep(text_delay)

    if rate_limit_hit:
        print(f"\n⚠️  Rate limits were hit during text-based tests.")
        print(f"Consider increasing text_delay (current: {text_delay}s)")

    print(f"\nWaiting 10 seconds before video-based tests...")
    time.sleep(10)

    # Run video-based feedback tests
    print("\nRunning video-based feedback tests...")
    rate_limit_hit = False

    for i, video_file in enumerate(video_files[:num_tests]):
        criteria = criteria_list[i % len(criteria_list)]
        feedback = test_feedbacks[criteria][1]  # Use different feedback
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
                rate_limit_hit = True
                print(f"  ⚠️  RATE LIMIT detected! Waiting 60 seconds...")
                time.sleep(60)

        # Delay between video tests
        if i < num_tests - 1:
            time.sleep(video_delay)

    if rate_limit_hit:
        print(f"\n⚠️  Rate limits were hit during video-based tests.")
        print(f"Consider increasing video_delay (current: {video_delay}s)")

    return results


def analyze_results(all_trials: List[Dict]) -> Dict:
    """
    Analyze experiment results across all trials
    """
    text_times = []
    video_times = []
    text_failures = 0
    video_failures = 0
    text_rate_limits = 0
    video_rate_limits = 0

    for trial in all_trials:
        for result in trial["text_based"]:
            if result.get("success"):
                text_times.append(result["elapsed_time"])
            else:
                text_failures += 1
                if result.get("error_type") == "rate_limit":
                    text_rate_limits += 1

        for result in trial["video_based"]:
            if result.get("success"):
                video_times.append(result["elapsed_time"])
            else:
                video_failures += 1
                if result.get("error_type") == "rate_limit":
                    video_rate_limits += 1

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
        }
    }

    if video_times and text_times:
        analysis["comparison"] = {
            "speedup_ratio": analysis["text_based"]["mean"] / analysis["video_based"]["mean"],
            "time_difference": analysis["video_based"]["mean"] - analysis["text_based"]["mean"],
            "faster_method": "text_based" if analysis["text_based"]["mean"] < analysis["video_based"]["mean"] else "video_based"
        }

    return analysis


def main():
    """
    Main experiment runner
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run feedback generation performance experiment")
    parser.add_argument("--trials", type=int, default=3, help="Number of trials to run (default: 3)")
    parser.add_argument("--tests", type=int, default=5, help="Number of videos to test per trial (default: 5)")
    parser.add_argument("--text-delay", type=int, default=7, help="Delay between text-based tests in seconds (default: 7)")
    parser.add_argument("--video-delay", type=int, default=10, help="Delay between video-based tests in seconds (default: 10)")
    args = parser.parse_args()

    num_trials = args.trials
    num_tests = args.tests
    text_delay = args.text_delay
    video_delay = args.video_delay

    print("="*60)
    print("Feedback Generation Performance Experiment")
    print("Text-based vs Video-based Comparison")
    print("="*60)

    # Setup paths
    script_dir = Path(__file__).parent
    video_dir = script_dir / "yt_shorts"
    output_dir = script_dir / "experiment_results"
    output_dir.mkdir(exist_ok=True)

    # Get list of video files
    video_files = sorted([f.name for f in video_dir.glob("*.mp4")])
    print(f"\nFound {len(video_files)} video files")

    # Load analysis_results.json to check which videos are analyzed
    analysis_results_path = script_dir.parent / "api" / "analysis_results.json"
    try:
        with open(analysis_results_path, "r", encoding="utf-8") as f:
            analysis_results = json.load(f)
        available_files = [f for f in video_files if f in analysis_results]
        print(f"Found {len(available_files)} videos with analysis results")
    except FileNotFoundError:
        print("ERROR: analysis_results.json not found. Please run analyze_with_text() first.")
        return

    if len(available_files) < 5:
        print(f"ERROR: Need at least 5 videos with analysis results. Found: {len(available_files)}")
        print("Please run video_to_text() and analyze_with_text() on the downloaded videos first.")
        return

    print("\n" + "="*60)
    print("Experiment Configuration")
    print("="*60)

    print(f"\nConfiguration:")
    print(f"  Trials: {num_trials}")
    print(f"  Tests per trial: {num_tests}")
    print(f"  Text delay: {text_delay}s")
    print(f"  Video delay: {video_delay}s")
    print(f"\nNote: If rate limits are hit, delays will be automatically increased for that test.")

    all_trials = []

    for trial_num in range(1, num_trials + 1):
        trial_results = run_single_trial(available_files, video_dir, trial_num, num_tests, text_delay, video_delay)
        all_trials.append(trial_results)

        # Save intermediate results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        trial_file = output_dir / f"trial_{trial_num}_{timestamp}.json"
        with open(trial_file, "w", encoding="utf-8") as f:
            json.dump(trial_results, f, ensure_ascii=False, indent=2)
        print(f"\nTrial {trial_num} results saved to: {trial_file}")

        # Wait between trials
        if trial_num < num_trials:
            print(f"\nWaiting 15 seconds before next trial...")
            time.sleep(15)

    # Analyze all results
    print("\n" + "="*60)
    print("Analyzing results...")
    print("="*60)

    analysis = analyze_results(all_trials)

    # Print summary
    print("\n" + "="*60)
    print("EXPERIMENT RESULTS SUMMARY")
    print("="*60)
    print(f"\nText-based approach:")
    print(f"  Tests completed: {analysis['text_based']['count']}")
    print(f"  Failures: {analysis['text_based']['failures']}")
    print(f"  Rate limit errors: {analysis['text_based']['rate_limit_errors']}")
    print(f"  Mean time: {analysis['text_based']['mean']:.3f}s")
    print(f"  Median time: {analysis['text_based']['median']:.3f}s")
    print(f"  Std dev: {analysis['text_based']['stdev']:.3f}s")
    print(f"  Range: {analysis['text_based']['min']:.3f}s - {analysis['text_based']['max']:.3f}s")

    print(f"\nVideo-based approach:")
    print(f"  Tests completed: {analysis['video_based']['count']}")
    print(f"  Failures: {analysis['video_based']['failures']}")
    print(f"  Rate limit errors: {analysis['video_based']['rate_limit_errors']}")
    print(f"  Mean time: {analysis['video_based']['mean']:.3f}s")
    print(f"  Median time: {analysis['video_based']['median']:.3f}s")
    print(f"  Std dev: {analysis['video_based']['stdev']:.3f}s")
    print(f"  Range: {analysis['video_based']['min']:.3f}s - {analysis['video_based']['max']:.3f}s")

    if "comparison" in analysis:
        print(f"\nComparison:")
        print(f"  Speedup ratio: {analysis['comparison']['speedup_ratio']:.2f}x")
        print(f"  Time difference: {analysis['comparison']['time_difference']:.3f}s")
        print(f"  Faster method: {analysis['comparison']['faster_method']}")

    # Check if rate limits were hit
    total_rate_limits = analysis['text_based']['rate_limit_errors'] + analysis['video_based']['rate_limit_errors']
    if total_rate_limits > 0:
        print(f"\n⚠️  WARNING: {total_rate_limits} rate limit errors occurred during the experiment.")
        print(f"Consider re-running with larger delays:")
        print(f"  Suggested text_delay: {text_delay + 2}s")
        print(f"  Suggested video_delay: {video_delay + 3}s")

    # Save final analysis
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_results = {
        "experiment_id": f"exp_{timestamp}",
        "configuration": {
            "num_trials": num_trials,
            "num_tests_per_trial": num_tests,
            "text_delay": text_delay,
            "video_delay": video_delay
        },
        "analysis": analysis,
        "all_trials": all_trials
    }

    final_file = output_dir / f"experiment_results_{timestamp}.json"
    with open(final_file, "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Final results saved to: {final_file}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
