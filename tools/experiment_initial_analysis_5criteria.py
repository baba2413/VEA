#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Experiment: Compare initial analysis time between text-based and video-based approaches
Using the ACTUAL production system structure: 5 criteria, one at a time
"""

import os
import sys
import json
import time
import re
import statistics
import argparse
import unicodedata
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from google import genai
from api.utils import load_environment, ensure_env


def load_prompts_and_considerations():
    """Load prompts.json and considerations.json"""
    script_dir = Path(__file__).parent

    with open(script_dir.parent / "api" / "prompts.json", "r", encoding="utf-8") as f:
        prompts = json.load(f)

    with open(script_dir.parent / "api" / "considerations.json", "r", encoding="utf-8") as f:
        considerations = json.load(f)

    return prompts, considerations


def load_ground_truth(ground_truth_path: Path) -> Optional[Dict]:
    """Load human-labeled ground truth data"""
    try:
        with open(ground_truth_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Remove _README or any other metadata entries
            return {k: v for k, v in data.items() if not k.startswith("_")}
    except FileNotFoundError:
        return None


def extract_prediction(result_text: str, criteria: str) -> Optional[int]:
    """
    Extract the 0/1 prediction from API response text
    Looks for patterns like "violence: 0" or "violence : 1"
    """
    # Pattern: criteria name followed by colon and 0 or 1
    pattern = rf"{criteria}\s*[:：]\s*([01])"
    match = re.search(pattern, result_text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # Fallback: just look for "0" or "1" at the start of a line
    lines = result_text.strip().split('\n')
    for line in lines[:3]:  # Check first 3 lines
        if line.strip() in ['0', '1']:
            return int(line.strip())

    return None


def calculate_accuracy_metrics(predictions: List[int], ground_truth: List[int]) -> Dict:
    """
    Calculate accuracy metrics: accuracy, precision, recall, F1
    Also returns confusion matrix components
    """
    if len(predictions) != len(ground_truth):
        return {"error": "Prediction and ground truth lengths don't match"}

    if not predictions:
        return {"error": "No predictions to evaluate"}

    # Confusion matrix components
    tp = sum(1 for p, g in zip(predictions, ground_truth) if p == 1 and g == 1)  # True Positives
    tn = sum(1 for p, g in zip(predictions, ground_truth) if p == 0 and g == 0)  # True Negatives
    fp = sum(1 for p, g in zip(predictions, ground_truth) if p == 1 and g == 0)  # False Positives
    fn = sum(1 for p, g in zip(predictions, ground_truth) if p == 0 and g == 1)  # False Negatives

    total = len(predictions)
    correct = tp + tn
    accuracy = correct / total if total > 0 else 0

    # Precision: TP / (TP + FP)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0

    # Recall: TP / (TP + FN)
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0

    # F1: 2 * (Precision * Recall) / (Precision + Recall)
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": {
            "true_positives": tp,
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn
        },
        "total_samples": total,
        "correct_predictions": correct
    }


def make_text_prompt(video_description: str, criteria: str, prompts: Dict, considerations: Dict) -> str:
    """
    Create prompt exactly like make_prompt() in gemini_test.py
    """
    prompt = f"""
{video_description}

{prompts[criteria]}

아래의 고려사항을 준수하여 심의한다.
고려사항: {considerations[criteria]}

반드시 출력 양식의 형태 그대로 출력한다.
출력 양식은 다은과 같다.
{criteria} : 0 or 1, 반드시 0 혹은 1의 값을 출력한다.
근거: 감지된 민감 요소 및 근거 서술. 단, 텍스트가 아닌 영상 원본을 본 것처럼 서술한다. 영상 요약은 하지 않으며, 2문장 내외로 서술한다.
"""
    return prompt


def run_text_based_analysis(video_description: str, criteria: str, prompts: Dict,
                            considerations: Dict, model: str = "gemini-2.5-flash") -> Tuple[str, float, bool, str]:
    """
    Run text-based analysis for ONE criteria
    Returns: (result, elapsed_time, success, error_type)
    """
    logger = logging.getLogger(__name__)
    start_time = time.perf_counter()
    try:
        logger.debug(f"Starting text-based analysis for criteria: {criteria}")
        client = genai.Client()
        prompt = make_text_prompt(video_description, criteria, prompts, considerations)

        resp = client.models.generate_content(
            model=model,
            contents=prompt
        )

        elapsed = time.perf_counter() - start_time
        logger.debug(f"Text-based analysis completed for {criteria} in {elapsed:.2f}s")

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
        if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
            error_type = "rate_limit"
        elif "BLOCKED" in error_str or "blocked_reason" in error_str.lower():
            error_type = "content_blocked"
        else:
            error_type = "other"
        logger.error(f"Text-based analysis failed for {criteria}: {error_type} - {error_str[:200]}")
        return error_str, elapsed, False, error_type


def run_video_based_analysis(video_path: str, criteria: str, prompts: Dict,
                             considerations: Dict, model: str = "gemini-2.5-flash") -> Tuple[str, float, bool, str]:
    """
    Run video-based analysis for ONE criteria
    Returns: (result, elapsed_time, success, error_type)
    """
    logger = logging.getLogger(__name__)
    start_time = time.perf_counter()
    try:
        logger.debug(f"Starting video-based analysis for criteria: {criteria}, video: {Path(video_path).name}")
        client = genai.Client()

        # Create prompt (without video description since we have the actual video)
        prompt = f"""
{prompts[criteria]}

아래의 고려사항을 준수하여 심의한다.
고려사항: {considerations[criteria]}

반드시 출력 양식의 형태 그대로 출력한다.
출력 양식은 다은과 같다.
{criteria} : 0 or 1, 반드시 0 혹은 1의 값을 출력한다.
근거: 감지된 민감 요소 및 근거 서술. 영상 요약은 하지 않으며, 2문장 내외로 서술한다.
"""

        # Upload video file
        logger.debug(f"Uploading video file: {Path(video_path).name}")
        file = client.files.upload(file=video_path)
        logger.debug(f"Video uploaded, file state: {file.state.name}, file name: {file.name}")

        # Wait for processing to complete
        wait_count = 0
        while file.state.name == "PROCESSING":
            time.sleep(1.0)
            wait_count += 1
            if wait_count % 10 == 0:  # Log every 10 seconds
                logger.debug(f"Still processing video after {wait_count}s: {Path(video_path).name}")
            file = client.files.get(name=file.name)

        logger.debug(f"Video processing complete, final state: {file.state.name}")
        if file.state.name != "ACTIVE":
            raise RuntimeError(f"Gemini file upload failed: state={file.state.name}")

        # Call API with video
        logger.debug(f"Calling API with video for criteria: {criteria}")
        resp = client.models.generate_content(
            model=model,
            contents=[file, prompt]
        )

        elapsed = time.perf_counter() - start_time
        logger.debug(f"Video-based analysis completed for {criteria} in {elapsed:.2f}s")

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
        if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
            error_type = "rate_limit"
        elif "BLOCKED" in error_str or "blocked_reason" in error_str.lower():
            error_type = "content_blocked"
        else:
            error_type = "other"
        logger.error(f"Video-based analysis failed for {criteria}: {error_type} - {error_str[:200]}")
        return error_str, elapsed, False, error_type


def run_single_trial(video_files: List[str], video_text_data: Dict, video_dir: Path,
                     prompts: Dict, considerations: Dict, trial_num: int, num_tests: int = 5,
                     text_delay: int = 7, video_delay: int = 10, original_names: Dict[str, str] = None) -> Dict:
    """
    Run a single trial - testing each video against 5 criteria
    """
    logger = logging.getLogger(__name__)
    print(f"\n{'='*60}")
    print(f"Trial {trial_num}")
    print(f"{'='*60}\n")
    logger.info(f"Starting trial {trial_num}")

    criteria_list = ["violence", "sexuality", "horror", "drugs", "language"]

    results = {
        "trial_number": trial_num,
        "timestamp": datetime.now().isoformat(),
        "text_delay": text_delay,
        "video_delay": video_delay,
        "text_based": [],
        "video_based": []
    }

    # Run text-based analysis tests (5 criteria per video)
    print("Running text-based analysis tests (5 criteria per video)...")
    logger.info(f"Starting text-based analysis for {num_tests} videos")
    rate_limit_hit = False

    for idx, video_file in enumerate(video_files[:num_tests], 1):
        if video_file not in video_text_data:
            print(f"  ⚠️  No description found for {video_file}, skipping...")
            logger.warning(f"No description found for {video_file}")
            continue

        logger.info(f"Processing text-based video {idx}/{num_tests}: {video_file}")
        video_description = video_text_data[video_file]

        for criteria in criteria_list:
            result, elapsed, success, error_type = run_text_based_analysis(
                video_description, criteria, prompts, considerations
            )

            results["text_based"].append({
                "video": video_file,
                "criteria": criteria,
                "elapsed_time": elapsed,
                "success": success,
                "result": result,  # Store full result for accuracy extraction
                "error_type": error_type
            })

            if success:
                print(f"  ✓ {video_file[:30]}... ({criteria}): {elapsed:.3f}s")
            else:
                print(f"  ✗ {video_file[:30]}... ({criteria}): {error_type}")
                if error_type == "rate_limit":
                    rate_limit_hit = True
                    print(f"  ⚠️  RATE LIMIT detected! Waiting 30 seconds...")
                    time.sleep(30)

            time.sleep(text_delay)

    if rate_limit_hit:
        print(f"\n⚠️  Rate limits were hit during text-based tests.")

    print(f"\nWaiting 10 seconds before video-based tests...")
    time.sleep(10)

    # Run video-based analysis tests (5 criteria per video)
    print("\nRunning video-based analysis tests (5 criteria per video)...")
    logger.info(f"Starting video-based analysis for {num_tests} videos")
    rate_limit_hit = False

    for idx, video_file in enumerate(video_files[:num_tests], 1):
        # Use original filename for filesystem access if mapping is provided
        filesystem_name = original_names.get(video_file, video_file) if original_names else video_file
        video_path = str(video_dir / filesystem_name)

        if not Path(video_path).exists():
            print(f"  ⚠️  Video file not found: {video_file}, skipping...")
            logger.warning(f"Video file not found: {video_file}")
            continue

        logger.info(f"Processing video-based video {idx}/{num_tests}: {video_file}")
        for criteria in criteria_list:
            result, elapsed, success, error_type = run_video_based_analysis(
                video_path, criteria, prompts, considerations
            )

            results["video_based"].append({
                "video": video_file,
                "criteria": criteria,
                "elapsed_time": elapsed,
                "success": success,
                "result": result,  # Store full result for accuracy extraction
                "error_type": error_type
            })

            if success:
                print(f"  ✓ {video_file[:30]}... ({criteria}): {elapsed:.3f}s")
            else:
                print(f"  ✗ {video_file[:30]}... ({criteria}): {error_type}")
                if error_type == "rate_limit":
                    rate_limit_hit = True
                    print(f"  ⚠️  RATE LIMIT detected! Waiting 60 seconds...")
                    time.sleep(60)

            time.sleep(video_delay)

    if rate_limit_hit:
        print(f"\n⚠️  Rate limits were hit during video-based tests.")

    logger.info(f"Trial {trial_num} completed successfully")
    return results


def analyze_results(all_trials: List[Dict], ground_truth: Optional[Dict] = None) -> Dict:
    """
    Analyze experiment results across all trials
    Includes both per-criteria and per-video (parallel) statistics
    If ground_truth is provided, also calculates accuracy metrics
    """
    text_times = []
    video_times = []
    text_failures = 0
    video_failures = 0
    text_rate_limits = 0
    video_rate_limits = 0
    text_blocked = 0
    video_blocked = 0

    # For per-video analysis (parallel execution)
    text_per_video = {}  # video_name -> [criteria_times]
    video_per_video = {}  # video_name -> [criteria_times]

    for trial in all_trials:
        for result in trial["text_based"]:
            if result.get("success"):
                text_times.append(result["elapsed_time"])
                video_name = result["video"]
                if video_name not in text_per_video:
                    text_per_video[video_name] = []
                text_per_video[video_name].append(result["elapsed_time"])
            else:
                text_failures += 1
                if result.get("error_type") == "rate_limit":
                    text_rate_limits += 1
                elif result.get("error_type") == "content_blocked":
                    text_blocked += 1

        for result in trial["video_based"]:
            if result.get("success"):
                video_times.append(result["elapsed_time"])
                video_name = result["video"]
                if video_name not in video_per_video:
                    video_per_video[video_name] = []
                video_per_video[video_name].append(result["elapsed_time"])
            else:
                video_failures += 1
                if result.get("error_type") == "rate_limit":
                    video_rate_limits += 1
                elif result.get("error_type") == "content_blocked":
                    video_blocked += 1

    # Calculate per-video times (max of 5 criteria for parallel execution)
    text_video_times = [max(times) for times in text_per_video.values() if len(times) == 5]
    video_video_times = [max(times) for times in video_per_video.values() if len(times) == 5]

    analysis = {
        "per_criteria": {
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
        },
        "per_video_parallel": {
            "text_based": {
                "count": len(text_video_times),
                "mean": statistics.mean(text_video_times) if text_video_times else 0,
                "median": statistics.median(text_video_times) if text_video_times else 0,
                "stdev": statistics.stdev(text_video_times) if len(text_video_times) > 1 else 0,
                "min": min(text_video_times) if text_video_times else 0,
                "max": max(text_video_times) if text_video_times else 0,
                "description": "Total time per video (max of 5 criteria, parallel execution)"
            },
            "video_based": {
                "count": len(video_video_times),
                "mean": statistics.mean(video_video_times) if video_video_times else 0,
                "median": statistics.median(video_video_times) if video_video_times else 0,
                "stdev": statistics.stdev(video_video_times) if len(video_video_times) > 1 else 0,
                "min": min(video_video_times) if video_video_times else 0,
                "max": max(video_video_times) if video_video_times else 0,
                "description": "Total time per video (max of 5 criteria, parallel execution)"
            }
        }
    }

    # Comparison - use per-criteria for detailed comparison
    if video_times and text_times:
        analysis["per_criteria"]["comparison"] = {
            "speedup_ratio": analysis["per_criteria"]["video_based"]["mean"] / analysis["per_criteria"]["text_based"]["mean"],
            "time_difference": analysis["per_criteria"]["video_based"]["mean"] - analysis["per_criteria"]["text_based"]["mean"],
            "faster_method": "text_based" if analysis["per_criteria"]["text_based"]["mean"] < analysis["per_criteria"]["video_based"]["mean"] else "video_based"
        }

    # Comparison - per-video (parallel)
    if video_video_times and text_video_times:
        analysis["per_video_parallel"]["comparison"] = {
            "speedup_ratio": analysis["per_video_parallel"]["video_based"]["mean"] / analysis["per_video_parallel"]["text_based"]["mean"],
            "time_difference": analysis["per_video_parallel"]["video_based"]["mean"] - analysis["per_video_parallel"]["text_based"]["mean"],
            "faster_method": "text_based" if analysis["per_video_parallel"]["text_based"]["mean"] < analysis["per_video_parallel"]["video_based"]["mean"] else "video_based"
        }

    # Calculate accuracy metrics if ground truth is provided
    if ground_truth:
        criteria_list = ["violence", "sexuality", "horror", "drugs", "language"]

        # Collect predictions and ground truth for text-based
        text_predictions = []
        text_ground_truth = []
        text_per_criteria_preds = {c: [] for c in criteria_list}
        text_per_criteria_truth = {c: [] for c in criteria_list}

        # Collect predictions and ground truth for video-based
        video_predictions = []
        video_ground_truth = []
        video_per_criteria_preds = {c: [] for c in criteria_list}
        video_per_criteria_truth = {c: [] for c in criteria_list}

        for trial in all_trials:
            # Process text-based results
            for result in trial["text_based"]:
                if result.get("success"):
                    video_name = result["video"]
                    criteria = result["criteria"]

                    if video_name in ground_truth and criteria in ground_truth[video_name]:
                        gt_value = ground_truth[video_name][criteria]
                        if gt_value is not None:  # Skip null values
                            pred = extract_prediction(result["result"], criteria)
                            if pred is not None:
                                text_predictions.append(pred)
                                text_ground_truth.append(gt_value)
                                text_per_criteria_preds[criteria].append(pred)
                                text_per_criteria_truth[criteria].append(gt_value)

            # Process video-based results
            for result in trial["video_based"]:
                if result.get("success"):
                    video_name = result["video"]
                    criteria = result["criteria"]

                    if video_name in ground_truth and criteria in ground_truth[video_name]:
                        gt_value = ground_truth[video_name][criteria]
                        if gt_value is not None:  # Skip null values
                            pred = extract_prediction(result["result"], criteria)
                            if pred is not None:
                                video_predictions.append(pred)
                                video_ground_truth.append(gt_value)
                                video_per_criteria_preds[criteria].append(pred)
                                video_per_criteria_truth[criteria].append(gt_value)

        # Calculate overall accuracy metrics
        analysis["accuracy"] = {
            "text_based": {
                "overall": calculate_accuracy_metrics(text_predictions, text_ground_truth) if text_predictions else None,
                "per_criteria": {}
            },
            "video_based": {
                "overall": calculate_accuracy_metrics(video_predictions, video_ground_truth) if video_predictions else None,
                "per_criteria": {}
            }
        }

        # Calculate per-criteria accuracy
        for criteria in criteria_list:
            if text_per_criteria_preds[criteria]:
                analysis["accuracy"]["text_based"]["per_criteria"][criteria] = calculate_accuracy_metrics(
                    text_per_criteria_preds[criteria], text_per_criteria_truth[criteria]
                )

            if video_per_criteria_preds[criteria]:
                analysis["accuracy"]["video_based"]["per_criteria"][criteria] = calculate_accuracy_metrics(
                    video_per_criteria_preds[criteria], video_per_criteria_truth[criteria]
                )

        # Add comparison
        if text_predictions and video_predictions:
            text_acc = analysis["accuracy"]["text_based"]["overall"]["accuracy"]
            video_acc = analysis["accuracy"]["video_based"]["overall"]["accuracy"]
            analysis["accuracy"]["comparison"] = {
                "text_accuracy": text_acc,
                "video_accuracy": video_acc,
                "accuracy_difference": video_acc - text_acc,
                "more_accurate_method": "text_based" if text_acc > video_acc else "video_based"
            }

    return analysis


def main():
    """
    Main experiment runner
    """
    # Setup logging
    log_dir = Path(__file__).parent / "experiment_logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # Create formatters
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # File handler - DEBUG level for detailed logs
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler - INFO level for cleaner output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[file_handler, console_handler]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting experiment - Log file: {log_file}")

    # Load environment variables from .env file
    try:
        load_environment()
        ensure_env("GOOGLE_API_KEY")
        logger.info("Environment loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load environment: {e}")
        raise

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run initial analysis performance experiment (5 criteria)")
    parser.add_argument("--trials", type=int, default=1, help="Number of trials to run (default: 1)")
    parser.add_argument("--tests", type=int, default=5, help="Number of videos to test per trial (default: 5)")
    parser.add_argument("--text-delay", type=int, default=7, help="Delay between text-based tests in seconds (default: 7)")
    parser.add_argument("--video-delay", type=int, default=10, help="Delay between video-based tests in seconds (default: 10)")
    parser.add_argument("--ground-truth", type=str, default=None, help="Path to ground truth JSON file for accuracy measurement")
    args = parser.parse_args()

    num_trials = args.trials
    num_tests = args.tests
    text_delay = args.text_delay
    video_delay = args.video_delay

    print("="*60)
    print("Initial Analysis Performance Experiment")
    print("5 Criteria Per Video - Text vs Video Comparison")
    print("="*60)

    # Setup paths
    script_dir = Path(__file__).parent
    video_dir = script_dir / "yt_shorts"
    video_text_path = script_dir / "video_text.json"
    output_dir = script_dir / "experiment_results"
    output_dir.mkdir(exist_ok=True)

    # Load prompts and considerations
    prompts, considerations = load_prompts_and_considerations()
    print(f"\nLoaded prompts for 5 criteria: {list(prompts.keys())}")

    # Load ground truth if provided
    ground_truth = None
    if args.ground_truth:
        ground_truth_path = Path(args.ground_truth)
        ground_truth = load_ground_truth(ground_truth_path)
        if ground_truth:
            print(f"Loaded ground truth data for {len(ground_truth)} videos")
        else:
            print(f"Warning: Could not load ground truth from {ground_truth_path}")
    else:
        print("No ground truth file provided - accuracy metrics will not be calculated")

    # Load video_text.json
    try:
        with open(video_text_path, "r", encoding="utf-8") as f:
            video_text_data = json.load(f)
        print(f"Loaded {len(video_text_data)} video descriptions from video_text.json")
    except FileNotFoundError:
        print("ERROR: video_text.json not found.")
        return

    # Normalize video_text_data keys to handle Unicode normalization issues (macOS NFD vs NFC)
    normalized_video_text = {unicodedata.normalize("NFC", k): v for k, v in video_text_data.items()}

    # Get list of video files - keep original names for filesystem access
    filesystem_files = list(video_dir.glob("*.mp4"))
    # Create mapping: normalized name -> original filesystem name
    original_names = {unicodedata.normalize("NFC", f.name): f.name for f in filesystem_files}

    # Get normalized file names for matching with video_text
    video_files_normalized = sorted([unicodedata.normalize("NFC", f.name) for f in filesystem_files])
    available_files = [f for f in video_files_normalized if f in normalized_video_text]

    print(f"Found {len(video_files_normalized)} video files")
    print(f"Found {len(available_files)} videos with descriptions")

    if len(available_files) < num_tests:
        print(f"ERROR: Need at least {num_tests} videos. Found: {len(available_files)}")
        return

    print("\n" + "="*60)
    print("Experiment Configuration")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  Trials: {num_trials}")
    print(f"  Videos per trial: {num_tests}")
    print(f"  Criteria per video: 5 (violence, sexuality, horror, drugs, language)")
    print(f"  Total API calls per trial: {num_tests * 5 * 2} ({num_tests * 5} text + {num_tests * 5} video)")
    print(f"  Text delay: {text_delay}s")
    print(f"  Video delay: {video_delay}s")

    all_trials = []

    for trial_num in range(1, num_trials + 1):
        trial_results = run_single_trial(available_files, normalized_video_text, video_dir,
                                        prompts, considerations,
                                        trial_num, num_tests, text_delay, video_delay, original_names)
        all_trials.append(trial_results)

        # Save intermediate results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        trial_file = output_dir / f"initial_5crit_trial_{trial_num}_{timestamp}.json"
        with open(trial_file, "w", encoding="utf-8") as f:
            json.dump(trial_results, f, ensure_ascii=False, indent=2)
        print(f"\nTrial {trial_num} results saved to: {trial_file}")

        if trial_num < num_trials:
            print(f"\nWaiting 15 seconds before next trial...")
            time.sleep(15)

    # Analyze all results
    print("\n" + "="*60)
    print("Analyzing results...")
    print("="*60)

    analysis = analyze_results(all_trials, ground_truth)

    # Print summary
    print("\n" + "="*60)
    print("EXPERIMENT RESULTS SUMMARY")
    print("="*60)

    print("\n" + "="*60)
    print("PER-CRITERIA ANALYSIS (Individual Criteria Times)")
    print("="*60)
    print(f"\nText-based approach:")
    print(f"  Tests completed: {analysis['per_criteria']['text_based']['count']}")
    print(f"  Failures: {analysis['per_criteria']['text_based']['failures']}")
    print(f"  Rate limit errors: {analysis['per_criteria']['text_based']['rate_limit_errors']}")
    print(f"  Content blocked: {analysis['per_criteria']['text_based']['content_blocked']}")
    print(f"  Mean time: {analysis['per_criteria']['text_based']['mean']:.3f}s")
    print(f"  Median time: {analysis['per_criteria']['text_based']['median']:.3f}s")
    print(f"  Std dev: {analysis['per_criteria']['text_based']['stdev']:.3f}s")
    print(f"  Range: {analysis['per_criteria']['text_based']['min']:.3f}s - {analysis['per_criteria']['text_based']['max']:.3f}s")

    print(f"\nVideo-based approach:")
    print(f"  Tests completed: {analysis['per_criteria']['video_based']['count']}")
    print(f"  Failures: {analysis['per_criteria']['video_based']['failures']}")
    print(f"  Rate limit errors: {analysis['per_criteria']['video_based']['rate_limit_errors']}")
    print(f"  Content blocked: {analysis['per_criteria']['video_based']['content_blocked']}")
    print(f"  Mean time: {analysis['per_criteria']['video_based']['mean']:.3f}s")
    print(f"  Median time: {analysis['per_criteria']['video_based']['median']:.3f}s")
    print(f"  Std dev: {analysis['per_criteria']['video_based']['stdev']:.3f}s")
    print(f"  Range: {analysis['per_criteria']['video_based']['min']:.3f}s - {analysis['per_criteria']['video_based']['max']:.3f}s")

    if "comparison" in analysis["per_criteria"]:
        print(f"\nPer-Criteria Comparison:")
        print(f"  Speedup ratio: {analysis['per_criteria']['comparison']['speedup_ratio']:.2f}x")
        print(f"  Time difference: {analysis['per_criteria']['comparison']['time_difference']:.3f}s")
        print(f"  Faster method: {analysis['per_criteria']['comparison']['faster_method']}")

    print("\n" + "="*60)
    print("PER-VIDEO ANALYSIS (Parallel Execution - Production Mode)")
    print("="*60)
    print(f"\nText-based approach (max of 5 criteria):")
    print(f"  Videos completed: {analysis['per_video_parallel']['text_based']['count']}")
    print(f"  Mean time: {analysis['per_video_parallel']['text_based']['mean']:.3f}s")
    print(f"  Median time: {analysis['per_video_parallel']['text_based']['median']:.3f}s")
    print(f"  Std dev: {analysis['per_video_parallel']['text_based']['stdev']:.3f}s")
    print(f"  Range: {analysis['per_video_parallel']['text_based']['min']:.3f}s - {analysis['per_video_parallel']['text_based']['max']:.3f}s")

    print(f"\nVideo-based approach (max of 5 criteria):")
    print(f"  Videos completed: {analysis['per_video_parallel']['video_based']['count']}")
    print(f"  Mean time: {analysis['per_video_parallel']['video_based']['mean']:.3f}s")
    print(f"  Median time: {analysis['per_video_parallel']['video_based']['median']:.3f}s")
    print(f"  Std dev: {analysis['per_video_parallel']['video_based']['stdev']:.3f}s")
    print(f"  Range: {analysis['per_video_parallel']['video_based']['min']:.3f}s - {analysis['per_video_parallel']['video_based']['max']:.3f}s")

    if "comparison" in analysis["per_video_parallel"]:
        print(f"\nPer-Video Comparison (Production Mode):")
        print(f"  Speedup ratio: {analysis['per_video_parallel']['comparison']['speedup_ratio']:.2f}x")
        print(f"  Time difference: {analysis['per_video_parallel']['comparison']['time_difference']:.3f}s")
        print(f"  Faster method: {analysis['per_video_parallel']['comparison']['faster_method']}")

    # Print accuracy results if available
    if "accuracy" in analysis:
        print("\n" + "="*60)
        print("ACCURACY ANALYSIS")
        print("="*60)

        # Overall accuracy
        if analysis["accuracy"]["text_based"]["overall"]:
            text_overall = analysis["accuracy"]["text_based"]["overall"]
            print(f"\nText-based approach (Overall):")
            print(f"  Samples evaluated: {text_overall['total_samples']}")
            print(f"  Correct predictions: {text_overall['correct_predictions']}")
            print(f"  Accuracy: {text_overall['accuracy']:.1%}")
            print(f"  Precision: {text_overall['precision']:.1%}")
            print(f"  Recall: {text_overall['recall']:.1%}")
            print(f"  F1 Score: {text_overall['f1']:.1%}")
            print(f"  Confusion Matrix:")
            print(f"    TP: {text_overall['confusion_matrix']['true_positives']}, "
                  f"TN: {text_overall['confusion_matrix']['true_negatives']}, "
                  f"FP: {text_overall['confusion_matrix']['false_positives']}, "
                  f"FN: {text_overall['confusion_matrix']['false_negatives']}")

        if analysis["accuracy"]["video_based"]["overall"]:
            video_overall = analysis["accuracy"]["video_based"]["overall"]
            print(f"\nVideo-based approach (Overall):")
            print(f"  Samples evaluated: {video_overall['total_samples']}")
            print(f"  Correct predictions: {video_overall['correct_predictions']}")
            print(f"  Accuracy: {video_overall['accuracy']:.1%}")
            print(f"  Precision: {video_overall['precision']:.1%}")
            print(f"  Recall: {video_overall['recall']:.1%}")
            print(f"  F1 Score: {video_overall['f1']:.1%}")
            print(f"  Confusion Matrix:")
            print(f"    TP: {video_overall['confusion_matrix']['true_positives']}, "
                  f"TN: {video_overall['confusion_matrix']['true_negatives']}, "
                  f"FP: {video_overall['confusion_matrix']['false_positives']}, "
                  f"FN: {video_overall['confusion_matrix']['false_negatives']}")

        # Comparison
        if "comparison" in analysis["accuracy"]:
            comp = analysis["accuracy"]["comparison"]
            print(f"\nAccuracy Comparison:")
            print(f"  Text-based accuracy: {comp['text_accuracy']:.1%}")
            print(f"  Video-based accuracy: {comp['video_accuracy']:.1%}")
            print(f"  Accuracy difference: {comp['accuracy_difference']:+.1%}")
            print(f"  More accurate method: {comp['more_accurate_method']}")

        # Per-criteria accuracy
        print(f"\nPer-Criteria Accuracy:")
        criteria_list = ["violence", "sexuality", "horror", "drugs", "language"]
        for criteria in criteria_list:
            text_crit = analysis["accuracy"]["text_based"]["per_criteria"].get(criteria)
            video_crit = analysis["accuracy"]["video_based"]["per_criteria"].get(criteria)

            if text_crit or video_crit:
                print(f"\n  {criteria.upper()}:")
                if text_crit:
                    print(f"    Text-based: {text_crit['accuracy']:.1%} "
                          f"(P: {text_crit['precision']:.1%}, R: {text_crit['recall']:.1%}, F1: {text_crit['f1']:.1%})")
                if video_crit:
                    print(f"    Video-based: {video_crit['accuracy']:.1%} "
                          f"(P: {video_crit['precision']:.1%}, R: {video_crit['recall']:.1%}, F1: {video_crit['f1']:.1%})")

    # Save final analysis
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_results = {
        "experiment_id": f"initial_5crit_{timestamp}",
        "description": "Initial analysis with 5 criteria (one at a time): text vs video",
        "configuration": {
            "num_trials": num_trials,
            "num_tests_per_trial": num_tests,
            "criteria_per_video": 5,
            "total_api_calls_per_trial": num_tests * 5 * 2,
            "text_delay": text_delay,
            "video_delay": video_delay
        },
        "analysis": analysis,
        "all_trials": all_trials
    }

    final_file = output_dir / f"initial_5crit_results_{timestamp}.json"
    with open(final_file, "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Final results saved to: {final_file}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
