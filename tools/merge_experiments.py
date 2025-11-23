#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge the original 5-video experiment with the remaining 13-video experiment
to create a comprehensive 18-video analysis
"""

import json
import statistics
from datetime import datetime
from pathlib import Path


def load_json(filepath):
    """Load JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data, filepath):
    """Save JSON file"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def merge_experiments():
    """Merge original 5-video and remaining 13-video experiments"""

    print("="*60)
    print("Merging Experiment Results")
    print("="*60)
    print()

    # Load original 5-video experiment (adjusted, with outlier removed)
    original_file = Path("experiment_results/experiment_results_adjusted.json")
    original_data = load_json(original_file)
    print(f"✓ Loaded original experiment: {original_file}")
    print(f"  - Videos tested: 5")
    print(f"  - Trials: {len(original_data['all_trials'])}")
    print()

    # Find the most recent remaining experiment results
    results_dir = Path("experiment_results")
    remaining_files = sorted(results_dir.glob("experiment_remaining_*.json"))

    if not remaining_files:
        print("❌ No remaining experiment results found!")
        print("   Please run experiment_remaining.py first.")
        return

    remaining_file = remaining_files[-1]  # Most recent
    remaining_data = load_json(remaining_file)
    print(f"✓ Loaded remaining experiment: {remaining_file}")
    print(f"  - Videos tested: {remaining_data['configuration']['num_tests_per_trial']}")
    print(f"  - Trials: {len(remaining_data['all_trials'])}")
    print()

    # Merge the trial data
    all_merged_trials = []

    # Add original trials (3 trials with 5 videos each)
    for trial in original_data['all_trials']:
        all_merged_trials.append(trial)

    # Add remaining trial (1 trial with 13 videos)
    # Renumber it to continue from original trials
    for trial in remaining_data['all_trials']:
        merged_trial = trial.copy()
        merged_trial['trial_number'] = len(original_data['all_trials']) + trial['trial_number']
        all_merged_trials.append(merged_trial)

    print(f"✓ Merged {len(all_merged_trials)} trials")
    print()

    # Collect all timing data
    text_times = []
    video_times = []
    text_failures = 0
    video_failures = 0
    text_rate_limits = 0
    video_rate_limits = 0

    for trial in all_merged_trials:
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

    print(f"✓ Collected timing data:")
    print(f"  - Text-based tests: {len(text_times)} successful, {text_failures} failed")
    print(f"  - Video-based tests: {len(video_times)} successful, {video_failures} failed")
    print()

    # Calculate merged statistics
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

    # Get list of all videos tested
    all_videos = set()
    for trial in all_merged_trials:
        for test in trial["text_based"]:
            all_videos.add(test["video"])

    # Create merged experiment data
    merged_data = {
        "experiment_id": f"merged_18videos_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "description": "Combined results from 5-video (3 trials) + 13-video (1 trial) experiments",
        "configuration": {
            "total_unique_videos": len(all_videos),
            "original_experiment": {
                "videos": 5,
                "trials": len(original_data['all_trials']),
                "text_delay": original_data['configuration']['text_delay'],
                "video_delay": original_data['configuration']['video_delay']
            },
            "remaining_experiment": {
                "videos": remaining_data['configuration']['num_tests_per_trial'],
                "trials": len(remaining_data['all_trials']),
                "text_delay": remaining_data['configuration']['text_delay'],
                "video_delay": remaining_data['configuration']['video_delay']
            }
        },
        "analysis": analysis,
        "all_trials": all_merged_trials,
        "videos_tested": sorted(list(all_videos))
    }

    # Save merged results
    merged_file = Path("experiment_results") / f"experiment_merged_18videos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_json(merged_data, merged_file)

    print("="*60)
    print("MERGED EXPERIMENT RESULTS - ALL 18 VIDEOS")
    print("="*60)
    print()

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

    print("="*60)
    print(f"Merged results saved to:")
    print(f"  {merged_file}")
    print("="*60)
    print()

    return merged_file


if __name__ == "__main__":
    merge_experiments()
