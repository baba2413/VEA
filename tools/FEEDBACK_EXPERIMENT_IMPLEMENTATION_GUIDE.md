# Feedback Experiment Implementation Guide

## Quick Start

The feedback experiment compares text-input vs video-input when user presses "피드백 반영" button.

**Status**: Foundation created in `experiment_feedback_comparison.py`
**Next**: Complete the 7 remaining functions below

## Implementation Checklist

### 1. Complete `feedback_with_text_input()` ✅ (Already done)
Uses video_text.json descriptions to process feedback.

### 2. Complete `feedback_with_video_input()` ✅ (Already done)
Uses actual video files to process feedback.

### 3. Add `re_analyze_with_text()` function
```python
def re_analyze_with_text(video_descriptions, prompts, considerations_updated, criteria_to_check):
    """Re-analyze all 20 videos using text descriptions with updated considerations"""
    # Load all 20 videos
    # For each video, for each changed criteria:
    #   - Create prompt with video_text + prompt + updated_considerations
    #   - Call analyze_with_gemini()
    #   - Parse result (0 or 1)
    # Use ThreadPoolExecutor with max_workers = min(8, len(tasks))
    # Return: {video: {criteria: result}}
```

### 4. Add `re_analyze_with_video()` function
```python
def re_analyze_with_video(video_dir, prompts, considerations_updated, criteria_to_check):
    """Re-analyze all 20 videos using video files with updated considerations"""
    # Similar to re_analyze_with_text but:
    #   - Upload video file
    #   - Create prompt with video + prompt + updated_considerations
    # Use ThreadPoolExecutor with max_workers = min(8, len(tasks))
    # Return: {video: {criteria: result}}
```

### 5. Add `calculate_accuracy()` function
```python
def calculate_accuracy(results, ground_truth):
    """Calculate accuracy metrics"""
    # Compare results vs ground_truth
    # Return: accuracy, precision, recall, F1, confusion matrix
```

### 6. Complete `main()` function
```python
def main():
    # Load data
    feedbacks = parse_feedbacks_from_file("incorrect_results_for_feedback.txt")
    video_descriptions = load("video_text.json")
    prompts = load("../api/prompts.json")
    considerations = load("../api/considerations.json")
    ground_truth = load("ground_truth_template.json")

    # Group feedbacks by criteria
    feedbacks_by_criteria = {}  # {criteria: [feedbacks...]}

    # TEXT-INPUT WORKFLOW
    print("TEXT-INPUT FEEDBACK WORKFLOW")

    # (a) Process all feedbacks
    text_feedback_time = 0
    text_processed_feedbacks = {}  # {criteria: [processed_feedbacks...]}
    for feedback in feedbacks:
        start = time.perf_counter()
        processed = feedback_with_text_input(...)
        text_feedback_time += time.perf_counter() - start
        time.sleep(DELAY_BETWEEN_CALLS)

    # (b) Update considerations
    start = time.perf_counter()
    considerations_text = update_considerations(considerations.copy(), text_processed_feedbacks)
    text_consideration_time = time.perf_counter() - start

    # (c) Re-analyze all 20 videos
    changed_criteria = list(text_processed_feedbacks.keys())
    start = time.perf_counter()
    text_results = re_analyze_with_text(video_descriptions, prompts, considerations_text, changed_criteria)
    text_reanalysis_time = time.perf_counter() - start

    # (d) Total
    text_total_time = text_feedback_time + text_consideration_time + text_reanalysis_time

    # VIDEO-INPUT WORKFLOW (same structure)
    print("VIDEO-INPUT FEEDBACK WORKFLOW")
    video_feedback_time = ...
    video_consideration_time = ...
    video_reanalysis_time = ...
    video_total_time = ...

    # (e) Calculate accuracy
    text_accuracy = calculate_accuracy(text_results, ground_truth)
    video_accuracy = calculate_accuracy(video_results, ground_truth)

    # Save results
    results = {
        "text_input": {
            "feedback_time": text_feedback_time,
            "consideration_time": text_consideration_time,
            "reanalysis_time": text_reanalysis_time,
            "total_time": text_total_time,
            "accuracy": text_accuracy
        },
        "video_input": {...},
        "comparison": {...}
    }

    with open(f"feedback_experiment_results_{datetime.now()}.json", "w") as f:
        json.dump(results, f, indent=2)

    # Print summary
    print_comparison_table(results)
```

### 7. Add `update_considerations()` helper
```python
def update_considerations(considerations, processed_feedbacks):
    """Append processed feedbacks to considerations"""
    updated = considerations.copy()
    for criteria, feedbacks in processed_feedbacks.items():
        updated[criteria] += "\n\n" + "\n".join(feedbacks)
    return updated
```

## Key Points

1. **Parallel Processing**: Use `max_workers = min(8, len(tasks))` for re-analysis
2. **Delays**: 2 seconds between API calls
3. **Deduplication**: The feedback file has duplicates - parse unique entries only
4. **Video Paths**: `yt_shorts/{video_filename}`
5. **Ground Truth**: Already validated, 100/100 samples

## Expected Output

```
TEXT-INPUT FEEDBACK WORKFLOW
  Processing 12 feedbacks...
  [1/12] Resident Evil - violence... 3.2s
  ...
  Total feedback time: 38.4s
  Updating considerations: 0.1s
  Re-analyzing 20 videos (5 criteria changed)... 245.8s
  Total: 284.3s

VIDEO-INPUT FEEDBACK WORKFLOW
  Processing 12 feedbacks...
  [1/12] Resident Evil - violence... 28.5s
  ...
  Total feedback time: 342.0s
  Updating considerations: 0.1s
  Re-analyzing 20 videos (5 criteria changed)... 536.4s
  Total: 878.5s

COMPARISON
  Text-input: 3.1x faster
  Text accuracy: 98.0% (+1.0% from initial 97.0%)
  Video accuracy: 93.0% (+2.0% from initial 91.0%)
```

## Files Needed

- `video_text.json` - Video descriptions ✓
- `../api/prompts.json` - Prompts ✓
- `../api/considerations.json` - Considerations ✓
- `ground_truth_template.json` - Ground truth ✓
- `incorrect_results_for_feedback.txt` - User feedbacks ✓
- `yt_shorts/*.mp4` - Video files ✓

All files are ready!

## Run Command

```bash
cd /Users/yj/Documents/GitHub/VEA/tools
python3 experiment_feedback_comparison.py
```

Expected runtime: ~1-2 hours (depending on API speed)
