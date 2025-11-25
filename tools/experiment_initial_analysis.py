#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Experiment: Compare initial analysis time between text-based and video-based approaches
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

from google import genai
from api.utils import load_environment, ensure_env

# Default prompt used for initial video analysis (from gemini_test.py)
DEFAULT_INITIAL_PROMPT = """
당신의 임무는 영상 등급 심의 전문가로서 주어진 30초 가량의 영상의 내용을 아래 7가지 기준에 따라 분석하고 평가하는 것아다.
영상의 장면, 대사, 음향, 분위기, 표현 방식 등을 종합적으로 고려하라.

[평가 기준]

1. 주제 및 내용: 사회 통념상 부적절하거나 불법, 차별, 비윤리적 행위를 미화·조장하는 주제가 포함되어 있는가?
2. 선정성: 노출, 성행위 묘사, 성적 자극을 유발하는 대사나 장면이 있는가?
3. 폭력성: 폭력 행위, 살상, 신체 훼손, 학대 등의 장면이 얼마나 자극적으로 표현되었는가?
4. 공포: 과도한 공포감, 혐오감, 불쾌감을 주는 장면이나 연출이 있는가?
5. 약물: 알코올, 마약, 흡연 등 약물 사용이 미화되거나 묘사되는가?
6. 언어: 비속어, 욕설, 차별적·혐오적 발언, 위협적 언어 표현이 있는가?
7. 모방 위험성: 위험하거나 비행을 조장할 수 있는 행위(폭력, 자해, 범죄 등)가 실제로 따라할 위험이 있는가?

각 기준에서 0에서 4까지의 점수를 매긴다. 0은 전체 이용가, 4는 청소년 이용불가 수준이다.

[출력 형식]
내용 요약: [영상 내용 요약]

1. 주제 및 내용: [점수(0~4)], [근거 또는 장면 설명]
2. 선정성: ...
3. 폭력성: ...
4. 공포: ...
5. 약물: ...
6. 언어: ...
7. 모방 위험성: ...

- 종합의견: [영상의 주요 문제 요약]

[주의]
분석 시 객관적 근거에 기반하여, 감정적 표현보다는 명확한 사실과 장면 묘사를 중심으로 작성한다.
반드시 출력 형식 외의 내용은 포함하지 않는다.
"""


def run_text_based_analysis(video_description: str, model: str = "gemini-2.5-flash") -> Tuple[str, float, bool, str]:
    """
    Run text-based initial analysis and measure time
    Returns: (result, elapsed_time, success, error_type)
    """
    start_time = time.perf_counter()
    try:
        client = genai.Client()

        # Create prompt with text description
        prompt = f"{video_description}\n\n{DEFAULT_INITIAL_PROMPT}"

        resp = client.models.generate_content(
            model=model,
            contents=prompt
        )

        elapsed = time.perf_counter() - start_time

        if hasattr(resp, "text") and resp.text:
            result = resp.text
        else:
            try:
                result = "\n".join(p.text for p in resp.candidates[0].content.parts if getattr(p, "text", None))
            except Exception:
                result = str(resp)

        return result, elapsed, True, None
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        error_str = str(e)
        # Check for rate limit or content moderation errors
        if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
            error_type = "rate_limit"
        elif "BLOCKED" in error_str or "blocked_reason" in error_str.lower():
            error_type = "content_blocked"
        else:
            error_type = "other"
        return error_str, elapsed, False, error_type


def run_video_based_analysis(video_path: str, model: str = "gemini-2.5-flash") -> Tuple[str, float, bool, str]:
    """
    Run video-based initial analysis and measure time
    Returns: (result, elapsed_time, success, error_type)
    """
    start_time = time.perf_counter()
    try:
        client = genai.Client()

        # Upload video file
        file = client.files.upload(file=video_path)

        # Wait for processing to complete
        while file.state.name == "PROCESSING":
            time.sleep(1.0)
            file = client.files.get(name=file.name)

        if file.state.name != "ACTIVE":
            raise RuntimeError(f"Gemini file upload failed: state={file.state.name}")

        # Call API with video
        resp = client.models.generate_content(
            model=model,
            contents=[file, DEFAULT_INITIAL_PROMPT]
        )

        elapsed = time.perf_counter() - start_time

        if hasattr(resp, "text") and resp.text:
            result = resp.text
        else:
            try:
                result = "\n".join(p.text for p in resp.candidates[0].content.parts if getattr(p, "text", None))
            except Exception:
                result = str(resp)

        return result, elapsed, True, None
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        error_str = str(e)
        # Check for rate limit or content moderation errors
        if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
            error_type = "rate_limit"
        elif "BLOCKED" in error_str or "blocked_reason" in error_str.lower():
            error_type = "content_blocked"
        else:
            error_type = "other"
        return error_str, elapsed, False, error_type


def run_single_trial(video_files: List[str], video_text_data: Dict, video_dir: Path,
                     trial_num: int, num_tests: int = 5,
                     text_delay: int = 7, video_delay: int = 10) -> Dict:
    """
    Run a single trial of the experiment

    Args:
        video_files: List of video filenames
        video_text_data: Dictionary mapping video names to descriptions
        video_dir: Directory containing videos
        trial_num: Trial number
        num_tests: Number of videos to test
        text_delay: Delay between text-based tests (seconds)
        video_delay: Delay between video-based tests (seconds)
    """
    print(f"\n{'='*60}")
    print(f"Trial {trial_num}")
    print(f"{'='*60}\n")

    results = {
        "trial_number": trial_num,
        "timestamp": datetime.now().isoformat(),
        "text_delay": text_delay,
        "video_delay": video_delay,
        "text_based": [],
        "video_based": []
    }

    # Run text-based initial analysis tests
    print("Running text-based initial analysis tests...")
    rate_limit_hit = False

    for i, video_file in enumerate(video_files[:num_tests]):
        # Get video description from video_text.json
        if video_file not in video_text_data:
            print(f"  ⚠️  No description found for {video_file}, skipping...")
            continue

        video_description = video_text_data[video_file]

        result, elapsed, success, error_type = run_text_based_analysis(video_description)
        results["text_based"].append({
            "video": video_file,
            "elapsed_time": elapsed,
            "success": success,
            "result": result[:200] if success else result,  # Truncate success results
            "error_type": error_type
        })

        if success:
            print(f"  ✓ {video_file[:40]}...: {elapsed:.3f}s")
        else:
            print(f"  ✗ {video_file[:40]}...: {error_type} - {result[:100]}")
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

    # Run video-based initial analysis tests
    print("\nRunning video-based initial analysis tests...")
    rate_limit_hit = False

    for i, video_file in enumerate(video_files[:num_tests]):
        video_path = str(video_dir / video_file)

        if not Path(video_path).exists():
            print(f"  ⚠️  Video file not found: {video_file}, skipping...")
            continue

        result, elapsed, success, error_type = run_video_based_analysis(video_path)
        results["video_based"].append({
            "video": video_file,
            "elapsed_time": elapsed,
            "success": success,
            "result": result[:200] if success else result,  # Truncate success results
            "error_type": error_type
        })

        if success:
            print(f"  ✓ {video_file[:40]}...: {elapsed:.3f}s")
        else:
            print(f"  ✗ {video_file[:40]}...: {error_type} - {result[:100]}")
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
    text_blocked = 0
    video_blocked = 0

    for trial in all_trials:
        for result in trial["text_based"]:
            if result.get("success"):
                text_times.append(result["elapsed_time"])
            else:
                text_failures += 1
                if result.get("error_type") == "rate_limit":
                    text_rate_limits += 1
                elif result.get("error_type") == "content_blocked":
                    text_blocked += 1

        for result in trial["video_based"]:
            if result.get("success"):
                video_times.append(result["elapsed_time"])
            else:
                video_failures += 1
                if result.get("error_type") == "rate_limit":
                    video_rate_limits += 1
                elif result.get("error_type") == "content_blocked":
                    video_blocked += 1

    analysis = {
        "text_based": {
            "count": len(text_times),
            "failures": text_failures,
            "rate_limit_errors": text_rate_limits,
            "content_blocked": text_blocked,
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
            "content_blocked": video_blocked,
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
            "speedup_ratio": analysis["video_based"]["mean"] / analysis["text_based"]["mean"],
            "time_difference": analysis["video_based"]["mean"] - analysis["text_based"]["mean"],
            "faster_method": "text_based" if analysis["text_based"]["mean"] < analysis["video_based"]["mean"] else "video_based"
        }

    return analysis


def main():
    """
    Main experiment runner
    """
    # Load environment variables from .env file
    load_environment()
    ensure_env("GOOGLE_API_KEY")

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run initial analysis performance experiment")
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
    print("Initial Analysis Performance Experiment")
    print("Text-based vs Video-based Comparison")
    print("="*60)

    # Setup paths
    script_dir = Path(__file__).parent
    video_dir = script_dir / "yt_shorts"
    video_text_path = script_dir / "video_text.json"
    output_dir = script_dir / "experiment_results"
    output_dir.mkdir(exist_ok=True)

    # Load video_text.json
    try:
        with open(video_text_path, "r", encoding="utf-8") as f:
            video_text_data = json.load(f)
        print(f"\nLoaded {len(video_text_data)} video descriptions from video_text.json")
    except FileNotFoundError:
        print("ERROR: video_text.json not found. Please run video_to_text() first.")
        return

    # Get list of video files that have both video files and descriptions
    video_files = sorted([f.name for f in video_dir.glob("*.mp4")])
    available_files = [f for f in video_files if f in video_text_data]

    print(f"Found {len(video_files)} video files")
    print(f"Found {len(available_files)} videos with descriptions")

    if len(available_files) < num_tests:
        print(f"ERROR: Need at least {num_tests} videos with descriptions. Found: {len(available_files)}")
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
        trial_results = run_single_trial(available_files, video_text_data, video_dir,
                                        trial_num, num_tests, text_delay, video_delay)
        all_trials.append(trial_results)

        # Save intermediate results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        trial_file = output_dir / f"initial_analysis_trial_{trial_num}_{timestamp}.json"
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
    print(f"  Content blocked: {analysis['text_based']['content_blocked']}")
    print(f"  Mean time: {analysis['text_based']['mean']:.3f}s")
    print(f"  Median time: {analysis['text_based']['median']:.3f}s")
    print(f"  Std dev: {analysis['text_based']['stdev']:.3f}s")
    print(f"  Range: {analysis['text_based']['min']:.3f}s - {analysis['text_based']['max']:.3f}s")

    print(f"\nVideo-based approach:")
    print(f"  Tests completed: {analysis['video_based']['count']}")
    print(f"  Failures: {analysis['video_based']['failures']}")
    print(f"  Rate limit errors: {analysis['video_based']['rate_limit_errors']}")
    print(f"  Content blocked: {analysis['video_based']['content_blocked']}")
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
        "experiment_id": f"initial_analysis_{timestamp}",
        "description": "Initial analysis performance comparison: text-based vs video-based",
        "configuration": {
            "num_trials": num_trials,
            "num_tests_per_trial": num_tests,
            "text_delay": text_delay,
            "video_delay": video_delay
        },
        "analysis": analysis,
        "all_trials": all_trials
    }

    final_file = output_dir / f"initial_analysis_results_{timestamp}.json"
    with open(final_file, "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Final results saved to: {final_file}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
