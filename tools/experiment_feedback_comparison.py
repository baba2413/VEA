#!/usr/bin/env python3
"""
Feedback Experiment: Compare Text-input vs Video-input Feedback Processing
Measures time and accuracy for feedback workflow when user presses "피드백 반영"
"""

import sys
import time
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from google import genai
from api.utils import load_environment, ensure_env

# Configuration
MODEL = "gemini-2.5-flash"
DELAY_BETWEEN_CALLS = 2  # seconds
# MAX_WORKERS will be calculated as min(8, len(tasks)) - same as original system

# Reuse previous video-based results instead of rerunning
REUSE_VIDEO_RESULTS = True
PREVIOUS_RESULTS_FILE = "experiment_results/feedback_experiment_20251125_200942.json"

def parse_feedbacks_from_file(feedback_file: str) -> List[Dict]:
    """Parse feedback entries from the template file"""
    with open(feedback_file, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'\[(\d+)\] (False \w+)\nVideo: (.+?)\nCriteria: (\w+)\nPredicted: (\d) \(should be (\d)\)\nFeedback: (.+?)(?=\n\n|\n\[|\Z)'
    matches = re.findall(pattern, content, re.DOTALL)

    feedbacks = []
    seen = set()  # Deduplicate (same video+criteria appears in both text/video sections)

    for match in matches:
        _, _, video, criteria, _, _, feedback_text = match
        feedback_text = feedback_text.strip()

        if feedback_text:
            key = (video, criteria)
            if key not in seen:
                feedbacks.append({
                    'video': video,
                    'criteria': criteria,
                    'feedback': feedback_text
                })
                seen.add(key)

    return feedbacks


def load_video_descriptions(video_text_file: str) -> Dict:
    """Load video descriptions for text-input version"""
    with open(video_text_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_initial_results(results_file: str) -> Dict:
    """Load initial analysis results"""
    with open(results_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_with_gemini(prompt: str, max_retries: int = 3) -> str:
    """Call Gemini API with retry logic"""
    client = genai.Client()

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt
            )
            return response.text if hasattr(response, 'text') else str(response)
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
                print(f"      API error (attempt {attempt + 1}/{max_retries}): {str(e)[:100]}")
                print(f"      Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                print(f"      ERROR after {max_retries} attempts: {str(e)[:200]}")
                return None


def feedback_with_text_input(video: str, criteria: str, feedback: str,
                             video_descriptions: Dict, initial_results: Dict) -> str:
    """
    Process feedback using TEXT input (video description)
    Simulates: feedback_with_llm() from gemini_test.py
    """
    # Get video description
    video_desc = video_descriptions.get(video, "")

    # Get initial analysis result (simulate getting from analysis_results)
    # For now, we'll use a simplified version

    prompt = f"""영상 심의 시스템의 유저가 영상을 보고 심의 내용에 대해 피드백을 작성하였다.
당신은 피드백의 내용을 영상의 맥락을 고려하여 재작성한다.

영상의 내용은 다음과 같다:
{video_desc}

이에 대한 유저의 피드백은 다음과 같다:
{feedback}

피드백의 의미를 유지하면서 영상의 맥락이 담길 수 있게끔 문장을 작성한다. 100자를 넘기지 않는다."""

    result = analyze_with_gemini(prompt)
    return result


def feedback_with_video_input(video_path: str, criteria: str, feedback: str) -> str:
    """
    Process feedback using VIDEO input (actual video file)
    NEW implementation - video-based version
    """
    client = genai.Client()

    # Upload video
    file = client.files.upload(file=video_path)

    # Wait for processing
    while file.state.name == "PROCESSING":
        time.sleep(1.0)
        file = client.files.get(name=file.name)

    if file.state.name != "ACTIVE":
        raise Exception(f"Video processing failed: {file.state.name}")

    # Generate refined feedback with video context
    prompt = f"""영상 심의 시스템의 유저가 영상을 보고 심의 내용에 대해 피드백을 작성하였다.
당신은 피드백의 내용을 영상의 맥락을 고려하여 재작성한다.

영상을 직접 보고 분석하시오.

이에 대한 유저의 피드백은 다음과 같다:
{feedback}

피드백의 의미를 유지하면서 영상의 맥락이 담길 수 있게끔 문장을 작성한다. 100자를 넘기지 않는다."""

    response = client.models.generate_content(
        model=MODEL,
        contents=[file, prompt]
    )

    return response.text if hasattr(response, 'text') else str(response)


def update_considerations(considerations: Dict, processed_feedbacks: Dict) -> Dict:
    """
    Append processed feedbacks to considerations
    """
    updated = considerations.copy()
    for criteria, feedbacks in processed_feedbacks.items():
        if feedbacks:  # Only update if there are feedbacks
            feedback_text = "\n".join(feedbacks)
            updated[criteria] += f"\n\n{feedback_text}"
    return updated


def extract_result_from_text(result_text: str, criteria: str) -> int:
    """Extract 0 or 1 from result text"""
    # Handle None or non-string input
    if result_text is None:
        print(f"      WARNING: result_text is None for criteria: {criteria}")
        return None

    # Convert to string if not already
    if not isinstance(result_text, str):
        result_text = str(result_text)

    # Try standard format: criteria : 0
    pattern = rf'{criteria}\s*:\s*(0|1)'
    match = re.search(pattern, result_text)
    if match:
        return int(match.group(1))

    # Try JSON format: "criteria": 0
    json_pattern = rf'"{criteria}"\s*:\s*(0|1)'
    match = re.search(json_pattern, result_text)
    if match:
        return int(match.group(1))

    # If no match found, log the result text for debugging
    print(f"      WARNING: Could not parse result for {criteria}. Response: {result_text[:200]}...")
    return None


def re_analyze_with_text(video_descriptions: Dict, prompts: Dict,
                         considerations_updated: Dict, criteria_to_check: List[str],
                         video_list: List[str] = None) -> Dict:
    """
    Re-analyze all 20 videos using text descriptions with updated considerations
    Returns: {video: {criteria: result}}
    """
    results = {}

    def analyze_one(video: str, criteria: str) -> Tuple[str, str, int]:
        """Analyze one video-criteria pair"""
        video_desc = video_descriptions.get(video, "")
        prompt_text = prompts[criteria]
        consideration = considerations_updated[criteria]

        full_prompt = f"""{prompt_text}

고려사항:
{consideration}

영상 내용:
{video_desc}

위 영상을 분석하고, 검열이 필요한 경우 1을, 필요하지 않은 경우 0을 출력한다.
출력 형식: {criteria} : 0 또는 1"""

        result_text = analyze_with_gemini(full_prompt)
        result_value = extract_result_from_text(result_text, criteria)

        return (video, criteria, result_value)

    # Create all tasks - use video_list if provided, otherwise all videos in video_descriptions
    tasks = []
    videos_to_analyze = video_list if video_list else list(video_descriptions.keys())
    for video in videos_to_analyze:
        for criteria in criteria_to_check:
            tasks.append((video, criteria))

    # Parallel execution with same settings as original system
    max_workers = min(8, len(tasks))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(analyze_one, video, criteria): (video, criteria)
                   for video, criteria in tasks}

        for future in as_completed(futures):
            video, criteria, result_value = future.result()
            if video not in results:
                results[video] = {}
            results[video][criteria] = result_value
            time.sleep(DELAY_BETWEEN_CALLS)

    return results


def re_analyze_with_video(video_dir: str, prompts: Dict,
                          considerations_updated: Dict, criteria_to_check: List[str]) -> Dict:
    """
    Re-analyze all 20 videos using video files with updated considerations
    Returns: {video: {criteria: result}}
    """
    results = {}

    # Get list of video files
    video_files = list(Path(video_dir).glob("*.mp4"))

    def analyze_one(video_path: Path, criteria: str) -> Tuple[str, str, int]:
        """Analyze one video-criteria pair"""
        # Create client inside function for thread safety
        client = genai.Client()

        # Upload video
        file = client.files.upload(file=str(video_path))

        # Wait for processing
        while file.state.name == "PROCESSING":
            time.sleep(1.0)
            file = client.files.get(name=file.name)

        if file.state.name != "ACTIVE":
            raise Exception(f"Video processing failed: {file.state.name}")

        prompt_text = prompts[criteria]
        consideration = considerations_updated[criteria]

        full_prompt = f"""{prompt_text}

고려사항:
{consideration}

위 영상을 직접 분석하고, 검열이 필요한 경우 1을, 필요하지 않은 경우 0을 출력한다.
출력 형식: {criteria} : 0 또는 1"""

        response = client.models.generate_content(
            model=MODEL,
            contents=[file, full_prompt]
        )

        result_text = response.text if hasattr(response, 'text') else str(response)
        result_value = extract_result_from_text(result_text, criteria)

        return (video_path.name, criteria, result_value)

    # Create all tasks
    tasks = []
    for video_path in video_files:
        for criteria in criteria_to_check:
            tasks.append((video_path, criteria))

    # Parallel execution
    max_workers = min(8, len(tasks))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(analyze_one, video_path, criteria): (video_path, criteria)
                   for video_path, criteria in tasks}

        for future in as_completed(futures):
            video, criteria, result_value = future.result()
            if video not in results:
                results[video] = {}
            results[video][criteria] = result_value
            time.sleep(DELAY_BETWEEN_CALLS)

    return results


def calculate_accuracy(results: Dict, ground_truth: Dict) -> Dict:
    """
    Calculate accuracy metrics
    Returns: {accuracy, precision, recall, f1, confusion_matrix}
    """
    tp = fp = tn = fn = 0

    # Filter out non-video entries from ground truth (_README, etc.)
    gt_filtered = {k: v for k, v in ground_truth.items() if k.endswith('.mp4')}

    for video, criteria_results in results.items():
        if video not in gt_filtered:
            continue

        for criteria, predicted in criteria_results.items():
            if criteria not in gt_filtered[video]:
                continue

            actual = gt_filtered[video][criteria]

            if predicted is None:
                continue

            if actual == 1 and predicted == 1:
                tp += 1
            elif actual == 0 and predicted == 1:
                fp += 1
            elif actual == 0 and predicted == 0:
                tn += 1
            elif actual == 1 and predicted == 0:
                fn += 1

    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "total_samples": total,
        "correct": tp + tn,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn
        }
    }


def print_comparison_table(results: Dict):
    """Print comparison table"""
    print()
    print("="*70)
    print("COMPARISON RESULTS")
    print("="*70)
    print()

    text = results["text_input"]
    video = results["video_input"]

    print("TIME COMPARISON:")
    print(f"  Text-input total:  {text['total_time']:.1f}s")
    print(f"  Video-input total: {video['total_time']:.1f}s")
    speedup = video['total_time'] / text['total_time'] if text['total_time'] > 0 else 0
    print(f"  → Text is {speedup:.2f}x faster")
    print()

    print("ACCURACY COMPARISON:")
    print(f"  Text-input:  {text['accuracy']['accuracy']*100:.1f}% ({text['accuracy']['correct']}/{text['accuracy']['total_samples']})")
    print(f"  Video-input: {video['accuracy']['accuracy']*100:.1f}% ({video['accuracy']['correct']}/{video['accuracy']['total_samples']})")
    print()


def main():
    from datetime import datetime

    print("="*70)
    print("FEEDBACK EXPERIMENT: Text-input vs Video-input")
    print("="*70)
    print()

    load_environment()
    ensure_env("GOOGLE_API_KEY")

    # Load data
    print("Loading data...")
    feedback_file = "incorrect_results_for_feedback.txt"
    feedbacks = parse_feedbacks_from_file(feedback_file)

    video_descriptions = load_video_descriptions("video_text.json")

    with open("../api/prompts.json", 'r', encoding='utf-8') as f:
        prompts = json.load(f)

    with open("../api/considerations.json", 'r', encoding='utf-8') as f:
        considerations = json.load(f)

    with open("ground_truth_template.json", 'r', encoding='utf-8') as f:
        ground_truth = json.load(f)

    print(f"✓ Parsed {len(feedbacks)} unique feedback entries")
    print(f"✓ Loaded {len(video_descriptions)} video descriptions")
    print(f"✓ Loaded {len(ground_truth)} ground truth entries")
    print()

    # Group feedbacks by criteria
    feedbacks_by_criteria = {}
    for fb in feedbacks:
        criteria = fb['criteria']
        if criteria not in feedbacks_by_criteria:
            feedbacks_by_criteria[criteria] = []
        feedbacks_by_criteria[criteria].append(fb)

    print(f"Feedback distribution: {', '.join(f'{k}: {len(v)}' for k, v in feedbacks_by_criteria.items())}")
    print()

    # ========================================================================
    # TEXT-INPUT WORKFLOW
    # ========================================================================
    print("="*70)
    print("TEXT-INPUT FEEDBACK WORKFLOW")
    print("="*70)
    print()

    # (a) Process all feedbacks
    print(f"(a) Processing {len(feedbacks)} feedbacks with TEXT input...")
    text_feedback_time = 0
    text_processed_feedbacks = {}  # {criteria: [processed_feedbacks...]}

    for i, feedback in enumerate(feedbacks, 1):
        video = feedback['video']
        criteria = feedback['criteria']
        feedback_text = feedback['feedback']

        print(f"  [{i}/{len(feedbacks)}] {video[:60]}... | {criteria}")

        start = time.perf_counter()
        try:
            processed = feedback_with_text_input(video, criteria, feedback_text,
                                                video_descriptions, {})
            if criteria not in text_processed_feedbacks:
                text_processed_feedbacks[criteria] = []
            text_processed_feedbacks[criteria].append(processed)
            elapsed = time.perf_counter() - start
            text_feedback_time += elapsed
            print(f"      → {elapsed:.1f}s")
        except Exception as e:
            print(f"      → ERROR: {e}")
            elapsed = time.perf_counter() - start
            text_feedback_time += elapsed

        time.sleep(DELAY_BETWEEN_CALLS)

    print(f"  Total feedback processing time: {text_feedback_time:.1f}s")
    print()

    # (b) Update considerations
    print("(b) Updating considerations with processed feedbacks...")
    start = time.perf_counter()
    considerations_text = update_considerations(considerations.copy(), text_processed_feedbacks)
    text_consideration_time = time.perf_counter() - start
    print(f"  → {text_consideration_time:.3f}s")
    print()

    # (c) Re-analyze all 20 videos
    # Get list of videos from yt_shorts directory (same as video-based approach)
    video_dir = "yt_shorts"
    video_files = list(Path(video_dir).glob("*.mp4"))
    video_list = [v.name for v in video_files]

    changed_criteria = list(text_processed_feedbacks.keys())
    print(f"(c) Re-analyzing all {len(video_list)} videos for {len(changed_criteria)} changed criteria...")
    print(f"    Criteria: {', '.join(changed_criteria)}")
    start = time.perf_counter()
    text_results = re_analyze_with_text(video_descriptions, prompts,
                                       considerations_text, changed_criteria, video_list)
    text_reanalysis_time = time.perf_counter() - start
    print(f"  → {text_reanalysis_time:.1f}s")
    print()

    # (d) Total
    text_total_time = text_feedback_time + text_consideration_time + text_reanalysis_time
    print(f"(d) TEXT-INPUT TOTAL TIME: {text_total_time:.1f}s")
    print()

    # ========================================================================
    # VIDEO-INPUT WORKFLOW
    # ========================================================================
    print("="*70)
    print("VIDEO-INPUT FEEDBACK WORKFLOW")
    print("="*70)
    print()

    if REUSE_VIDEO_RESULTS:
        print(f"⏩ REUSING previous video-based results from: {PREVIOUS_RESULTS_FILE}")
        print()

        with open(PREVIOUS_RESULTS_FILE, 'r', encoding='utf-8') as f:
            prev_results = json.load(f)

        video_feedback_time = prev_results["video_input"]["feedback_time"]
        video_consideration_time = prev_results["video_input"]["consideration_time"]
        video_reanalysis_time = prev_results["video_input"]["reanalysis_time"]
        video_total_time = prev_results["video_input"]["total_time"]
        video_accuracy = prev_results["video_input"]["accuracy"]
        video_processed_feedbacks = prev_results["video_input"]["processed_feedbacks"]
        video_results = prev_results["video_input"]["results"]

        print(f"  Loaded video-input data:")
        print(f"    Feedback time: {video_feedback_time:.1f}s")
        print(f"    Re-analysis time: {video_reanalysis_time:.1f}s")
        print(f"    Total time: {video_total_time:.1f}s")
        print(f"    Videos analyzed: {len(video_results)}")
        print()
    else:
        video_dir = "yt_shorts"

        # (a) Process all feedbacks
        print(f"(a) Processing {len(feedbacks)} feedbacks with VIDEO input...")
        video_feedback_time = 0
        video_processed_feedbacks = {}  # {criteria: [processed_feedbacks...]}

        for i, feedback in enumerate(feedbacks, 1):
            video = feedback['video']
            criteria = feedback['criteria']
            feedback_text = feedback['feedback']
            video_path = f"{video_dir}/{video}"

            print(f"  [{i}/{len(feedbacks)}] {video[:60]}... | {criteria}")

            start = time.perf_counter()
            try:
                processed = feedback_with_video_input(video_path, criteria, feedback_text)
                if criteria not in video_processed_feedbacks:
                    video_processed_feedbacks[criteria] = []
                video_processed_feedbacks[criteria].append(processed)
                elapsed = time.perf_counter() - start
                video_feedback_time += elapsed
                print(f"      → {elapsed:.1f}s")
            except Exception as e:
                print(f"      → ERROR: {e}")
                elapsed = time.perf_counter() - start
                video_feedback_time += elapsed

            time.sleep(DELAY_BETWEEN_CALLS)

        print(f"  Total feedback processing time: {video_feedback_time:.1f}s")
        print()

        # (b) Update considerations
        print("(b) Updating considerations with processed feedbacks...")
        start = time.perf_counter()
        considerations_video = update_considerations(considerations.copy(), video_processed_feedbacks)
        video_consideration_time = time.perf_counter() - start
        print(f"  → {video_consideration_time:.3f}s")
        print()

        # (c) Re-analyze all 20 videos
        changed_criteria_video = list(video_processed_feedbacks.keys())
        print(f"(c) Re-analyzing all 20 videos for {len(changed_criteria_video)} changed criteria...")
        print(f"    Criteria: {', '.join(changed_criteria_video)}")
        start = time.perf_counter()
        video_results = re_analyze_with_video(video_dir, prompts,
                                             considerations_video, changed_criteria_video)
        video_reanalysis_time = time.perf_counter() - start
        print(f"  → {video_reanalysis_time:.1f}s")
        print()

        # (d) Total
        video_total_time = video_feedback_time + video_consideration_time + video_reanalysis_time
        print(f"(d) VIDEO-INPUT TOTAL TIME: {video_total_time:.1f}s")
        print()

    # ========================================================================
    # CALCULATE ACCURACY
    # ========================================================================
    print("="*70)
    print("CALCULATING ACCURACY")
    print("="*70)
    print()

    print("Text-input accuracy:")
    text_accuracy = calculate_accuracy(text_results, ground_truth)
    print(f"  Accuracy: {text_accuracy['accuracy']*100:.1f}% ({text_accuracy['correct']}/{text_accuracy['total_samples']})")
    print(f"  Precision: {text_accuracy['precision']*100:.1f}%")
    print(f"  Recall: {text_accuracy['recall']*100:.1f}%")
    print(f"  F1: {text_accuracy['f1']*100:.1f}%")
    print()

    print("Video-input accuracy:")
    if not REUSE_VIDEO_RESULTS:
        video_accuracy = calculate_accuracy(video_results, ground_truth)
    # else: video_accuracy already loaded from previous results
    print(f"  Accuracy: {video_accuracy['accuracy']*100:.1f}% ({video_accuracy['correct']}/{video_accuracy['total_samples']})")
    print(f"  Precision: {video_accuracy['precision']*100:.1f}%")
    print(f"  Recall: {video_accuracy['recall']*100:.1f}%")
    print(f"  F1: {video_accuracy['f1']*100:.1f}%")
    print()

    # ========================================================================
    # SAVE RESULTS
    # ========================================================================
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {
        "experiment": "feedback_comparison",
        "timestamp": timestamp,
        "feedbacks_processed": len(feedbacks),
        "text_input": {
            "feedback_time": text_feedback_time,
            "consideration_time": text_consideration_time,
            "reanalysis_time": text_reanalysis_time,
            "total_time": text_total_time,
            "accuracy": text_accuracy,
            "processed_feedbacks": text_processed_feedbacks,
            "results": text_results
        },
        "video_input": {
            "feedback_time": video_feedback_time,
            "consideration_time": video_consideration_time,
            "reanalysis_time": video_reanalysis_time,
            "total_time": video_total_time,
            "accuracy": video_accuracy,
            "processed_feedbacks": video_processed_feedbacks,
            "results": video_results
        },
        "comparison": {
            "speedup": video_total_time / text_total_time if text_total_time > 0 else 0,
            "accuracy_difference": text_accuracy['accuracy'] - video_accuracy['accuracy']
        }
    }

    output_file = f"experiment_results/feedback_experiment_{timestamp}.json"
    with open(output_file, "w", encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Results saved to: {output_file}")

    # Print summary
    print_comparison_table(results)

    print()
    print("="*70)
    print("EXPERIMENT COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()
