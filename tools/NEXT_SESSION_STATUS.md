# VEA Project - Next Session Status

## Project Overview

**VEA (Video Evidence Analysis)** is a video content moderation system that uses LLM-based analysis to detect policy violations across 5 criteria:
- Violence (폭력성)
- Sexuality (선정성)
- Horror (공포)
- Drugs (약물)
- Language (언어)

**Key Innovation**: The system compares **text-based** (video → description → moderation) vs **video-based** (video → moderation) approaches.

## Completed Work

### 1. Initial Analysis Experiment ✅
**Script**: `experiment_initial_analysis_5criteria.py`

**Results** (from `initial_5crit_results_20251125_152732.json` and `EXPERIMENT_REPORT_20251125.md`):
- Dataset: 20 videos × 5 criteria = 100 samples
- All 200 API calls successful (100 text-based + 100 video-based)

**Performance**:
- Text-based: 12.08s per video (parallel execution)
- Video-based: 26.82s per video
- **Text is 2.22x faster** (without preprocessing cost)

**Accuracy** (validated against `ground_truth_template.json`):
- **Text-based: 97.0%** (97/100) - Precision 89.3%, Recall 100%, F1 94.3%
- **Video-based: 91.0%** (91/100) - Precision 75.0%, Recall 96.0%, F1 84.2%
- **Text is 6.0% more accurate**

**Key Finding**: Text-based has PERFECT recall (100%) - catches ALL violations without missing any.

### 2. Preprocessing Time Measurement ✅
**Script**: `measure_preprocessing_time.py`

**Results**:
- Average preprocessing time: 37.47s per video (to generate descriptions)
- With preprocessing: Text is 1.85x SLOWER for first-time analysis (49.55s vs 26.82s)
- Break-even: After 2nd check, text becomes faster
- Preprocessing is one-time cost; descriptions reused for all checks

### 3. Ground Truth Corrections ✅
- Fixed Wolverine video Unicode mismatch (curly apostrophe → straight apostrophe)
- Corrected Pulp Fiction violence ground truth (1 → 0) per user feedback
- All 100/100 samples now included in accuracy calculation

### 4. Feedback Collection ✅
**File**: `incorrect_results_for_feedback.txt`

User provided feedback for:
- 3 text-based errors (all false positives)
- 9 video-based errors (8 false positives, 1 false negative)

**Feedback examples**:
1. Resident Evil jump scare (violence FP): "직접적인 폭력이 등장하지 않고, 상처가 경미한 수준입니다..."
2. Breaking Bad "shit" (language FP): "한 번만 등장했고, 반복적인 사용이 아니었습니다..."
3. Thomas Shelby smoking (drugs FN): "담배를 멋있게 피는 장면이 직접적으로 클로즈업 되어서 나타나 미화의 가능성이 있고..."

## Current Task: Feedback Experiment

### Goal
Compare **text-input** vs **video-input** feedback processing when user presses "피드백 반영" button.

### What to Measure
Simulating the production workflow from button press to results:

**(a) Feedback making process**
- Text-input: Use video_text.json descriptions
- Video-input: Use actual video files
- Function: Convert raw user feedback → structured feedback with video context

**(b) Feedback to consideration**
- Same for both approaches
- Append processed feedback to considerations.json

**(c) Re-analyze all 20 videos**
- Use parallel processing (max_workers = min(8, len(tasks)))
- Text-input: Re-run with updated considerations using descriptions
- Video-input: Re-run with updated considerations using video files

**(d) Total time**: (a) + (b) + (c)

**(e) Accuracy comparison**
- Post-feedback results vs ground_truth_template.json
- Check how many errors were fixed by feedback

### Implementation Status

**Created**: `experiment_feedback_comparison.py` (foundation only)

**Completed**:
- ✅ Parse feedback from file (12 unique feedback entries)
- ✅ Configuration matches original system
- ✅ Basic structure with text-input and video-input functions

**TODO**:
1. Complete `feedback_with_text_input()` implementation
2. Complete `feedback_with_video_input()` implementation
3. Implement `feedback_to_consideration()` - append to considerations
4. Implement parallel re-analysis for both approaches
5. Measure timing for each phase (a, b, c, d)
6. Calculate post-feedback accuracy
7. Generate comparison report

### Key Files

**Data Files**:
- `yt_shorts/*.mp4` - 20 video files
- `video_text.json` - Preprocessed video descriptions
- `ground_truth_template.json` - Human-labeled ground truth (100 samples)
- `incorrect_results_for_feedback.txt` - User feedback for 12 cases
- `experiment_results/initial_5crit_results_20251125_152732.json` - Initial analysis results

**Code Files**:
- `experiment_initial_analysis_5criteria.py` - Initial experiment (COMPLETED)
- `measure_preprocessing_time.py` - Preprocessing measurement (COMPLETED)
- `experiment_feedback_comparison.py` - Feedback experiment (IN PROGRESS)
- `/Users/yj/Documents/GitHub/VEA/api/gemini_test.py` - Production system (reference)

**Report Files**:
- `experiment_results/EXPERIMENT_REPORT_20251125.md` - Comprehensive report

### Reference: Original System Architecture

From `/Users/yj/Documents/GitHub/VEA/api/gemini_test.py`:

1. **feedback_with_llm(file_name, criteria, feedback)**:
   - Line 143-172
   - Uses video_text for context
   - Calls LLM to refine user feedback
   - Appends to feedbacks.json

2. **feedback_to_consideration(criteria)**:
   - Line 174-195
   - Combines all feedback for a criteria
   - Updates considerations.json

3. **re_analyze()**:
   - Line 284-337
   - Parallel execution: `max_workers = min(8, len(tasks))`
   - Re-analyzes all videos for changed criteria
   - Returns updated results

### Next Steps

1. **Implement complete feedback workflow**:
   ```python
   # Phase (a): Process each feedback
   for feedback in feedbacks:
       text_time = measure(feedback_with_text_input(...))
       video_time = measure(feedback_with_video_input(...))

   # Phase (b): Update considerations
   feedback_to_consideration_time = measure(update_considerations(...))

   # Phase (c): Re-analyze all 20 videos
   text_reanalysis_time = measure(re_analyze_text_based(...))
   video_reanalysis_time = measure(re_analyze_video_based(...))

   # Phase (d): Calculate totals
   text_total = text_time + feedback_to_consideration_time + text_reanalysis_time
   video_total = video_time + feedback_to_consideration_time + video_reanalysis_time
   ```

2. **Calculate post-feedback accuracy**:
   - Compare new results against ground_truth_template.json
   - Check improvement in error cases
   - Report accuracy changes

3. **Generate comparison report**:
   - Time breakdown by phase
   - Per-video time (parallel execution)
   - Total refresh time
   - Accuracy improvements
   - Cost-benefit analysis

### Important Notes

- **API Rate Limit**: Use 2-second delays between calls
- **Parallel Processing**: Same as production (max_workers = min(8, len(tasks)))
- **Ground Truth**: Already corrected and validated (100/100 samples)
- **Model**: gemini-2.5-flash (same as all experiments)

### Expected Outcomes

Based on initial analysis patterns:
- Text-input likely faster for feedback processing (no video upload)
- Video-input provides direct video context (may be more accurate)
- Re-analysis time similar to initial analysis (12.08s vs 26.82s per video)
- Both approaches should improve accuracy on feedback cases

## Questions to Clarify Next Session

None - all requirements are clear. The feedback experiment workflow is well-defined based on the production system architecture.

---

**Status**: Ready to implement complete feedback experiment
**Estimated Time**: ~1-2 hours to run full experiment (12 feedbacks × 2 approaches + re-analysis)
**Priority**: High - this completes the core comparison between text-input and video-input approaches
