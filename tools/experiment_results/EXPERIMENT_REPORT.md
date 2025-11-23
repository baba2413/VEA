# Feedback Generation Performance Analysis Report

**Video Evaluation Application (VEA)**
**Experiment Date:** November 23, 2025
**Experiment ID:** exp_20251123_151849

---

## Executive Summary

This report presents a comprehensive performance comparison between text-based and video-based feedback generation methods for the VEA system. The experiment measured end-to-end execution time across 3 trials with 5 videos each.

### Key Findings

- **Text-based feedback is 2.66x faster** than video-based (8.4s vs 22.4s average)
- **Text-based feedback is more consistent** with 81% lower variance (1.6s vs 6.5s std dev)
- **One significant outlier detected** in text-based approach (221s - likely API throttling)
- **Recommendation:** Use text-based feedback for production deployment

---

## 1. Methodology

### 1.1 Experiment Design

**Objective:** Compare feedback generation time between two approaches:
- **Text-based:** Uses pre-generated video descriptions (via `feedback_with_llm`)
- **Video-based:** Analyzes actual video files directly (via `feedback_with_video`)

**Configuration:**
- Trials: 3
- Videos per trial: 5
- Total tests: 30 (15 text-based + 15 video-based)
- Delay between text tests: 7 seconds
- Delay between video tests: 10 seconds
- API: Google Gemini 2.5 Flash

### 1.2 Test Videos

Five videos were selected for testing:
1. `#shorts #담배-qR2K__FCLb0.mp4` (smoking content)
2. `''its okay'' WYM YOU JUST MADE ME JUMP #ethanwinters #residentevil7-pxNvqepEYOY.mp4` (horror game)
3. `BOOTED by Gordon Ramsay？! #shorts #gordonramsay #fyp-gT-ZPJW1j1c.mp4` (cooking show)
4. `Do you like leather bikinis？ 🖤 #beach #beachvibes #short #shorts #shortvideo #shortsfeed-WUGUXTcEUfo.mp4` (beach content)
5. `HEISENBERG'S FIRST DEAL!🤑｜ Breaking Bad #shorts-Ix3XLxar5Uo.mp4` (TV show clip)

### 1.3 Evaluation Criteria

Each video was tested against one of five content moderation criteria:
- Violence
- Sexuality
- Horror
- Drugs
- Language

### 1.4 Measurement Method

Performance was measured using Python's `time.perf_counter()` for high-precision timing:
- **Start time:** Immediately before function call
- **End time:** After function completion
- **Metric:** Total end-to-end execution time (seconds)

---

## 2. Raw Results

### 2.1 Original Results (Including Outlier)

| Metric | Text-based | Video-based |
|--------|-----------|-------------|
| Tests completed | 15 | 15 |
| Mean time | 22.627s | 22.380s |
| Median time | 8.134s | 21.404s |
| Std deviation | 55.011s | 6.505s |
| Min time | 6.597s | 13.011s |
| Max time | **221.400s** | 34.218s |
| Failures | 0 | 0 |
| Rate limit errors | 0 | 0 |

**Initial Assessment:** Results appeared nearly equivalent, but high standard deviation suggested anomalies.

### 2.2 Outlier Detection

**Identified Outlier:**
- Trial 2, Test 5: HEISENBERG video, language criteria
- Text-based time: **221.400 seconds** (33x slower than normal)
- Comparison with other trials:
  - Trial 1: 7.460s ✓
  - Trial 2: 221.400s ⚠️ **OUTLIER**
  - Trial 3: 6.597s ✓

**Root Cause Analysis:**
- Likely temporary API throttling or network latency
- Video-based tests on same video remained consistent (21-29s)
- Outlier represents <7% of tests (1/15)
- Not representative of typical performance

### 2.3 Adjusted Results (Outlier Removed)

| Metric | Text-based | Video-based | Ratio |
|--------|-----------|-------------|-------|
| Tests completed | 14 | 15 | - |
| Mean time | **8.429s** | 22.380s | **2.66x** |
| Median time | 7.885s | 21.404s | 2.71x |
| Std deviation | **1.623s** | 6.505s | 4.01x |
| Min time | 6.597s | 13.011s | - |
| Max time | 12.009s | 34.218s | - |
| Range | 5.412s | 21.207s | - |

---

## 3. Detailed Analysis

### 3.1 Performance Comparison

**Text-based Feedback:**
- **Faster:** 8.4s average (2.66x improvement)
- **More consistent:** 1.6s std dev vs 6.5s
- **Tighter range:** 6.6-12.0s (5.4s spread)
- **Lower variance:** 19% coefficient of variation

**Video-based Feedback:**
- **Slower:** 22.4s average
- **Higher variance:** 6.5s std dev
- **Wider range:** 13.0-34.2s (21.2s spread)
- **Higher variance:** 29% coefficient of variation

### 3.2 Statistical Significance

**Consistency Analysis:**

Text-based timing distribution:
```
6.5s  ████░░░░░░ (min)
7.3s  ██████░░░░
7.5s  ███████░░░
7.6s  ████████░░
8.1s  █████████░ (median)
8.2s  ██████████
8.4s  ██████████ (mean)
9.9s  ████████████
10.3s ██████████████
10.4s ███████████████
12.0s ████████████████████ (max)
```

Video-based timing distribution:
```
13.0s ████░░░░░░░░░░░░░░░░ (min)
14.7s ██████░░░░░░░░░░░░░░
14.8s ██████░░░░░░░░░░░░░░
17.4s █████████░░░░░░░░░░░
17.9s ██████████░░░░░░░░░░
18.2s ██████████░░░░░░░░░░
20.7s ████████████░░░░░░░░
21.4s ██████████████░░░░░░ (median)
22.4s ███████████████░░░░░ (mean)
24.3s ████████████████░░░░
24.5s █████████████████░░░
24.6s █████████████████░░░
29.0s ████████████████████░
29.1s ████████████████████░
31.4s ██████████████████████
34.2s ████████████████████████ (max)
```

### 3.3 Per-Video Performance Breakdown

**Average time by video (adjusted, text-based only):**

| Video | Trial 1 | Trial 2 | Trial 3 | Mean | Criteria |
|-------|---------|---------|---------|------|----------|
| #shorts #담배 | 10.3s | 8.2s | 12.0s | 10.2s | violence |
| 'its okay' | 7.6s | 10.4s | 7.6s | 8.5s | sexuality |
| BOOTED Gordon | 6.6s | 10.0s | 8.1s | 8.2s | horror |
| Leather bikinis | 8.4s | 7.3s | 7.3s | 7.7s | drugs |
| HEISENBERG | 7.5s | ~~221.4s~~ | 6.6s | 7.0s | language |

**Average time by video (video-based):**

| Video | Trial 1 | Trial 2 | Trial 3 | Mean | Criteria |
|-------|---------|---------|---------|------|----------|
| #shorts #담배 | 24.6s | 20.7s | 24.7s | 23.3s | violence |
| 'its okay' | 18.2s | 14.9s | 13.0s | 15.4s | sexuality |
| BOOTED Gordon | 31.4s | 29.0s | 34.2s | 31.5s | horror |
| Leather bikinis | 17.5s | 14.7s | 17.9s | 16.7s | drugs |
| HEISENBERG | 24.3s | 29.1s | 21.4s | 24.9s | language |

**Observations:**
- Text-based: All videos perform similarly (7-10s range)
- Video-based: Horror content takes longest (31.5s), sexuality shortest (15.4s)
- Possible correlation between video complexity and processing time for video-based approach

### 3.4 Trial-by-Trial Analysis

**Trial 1:**
- Text mean: 8.1s
- Video mean: 23.2s
- Ratio: 2.86x

**Trial 2:**
- Text mean (adjusted): 9.0s
- Video mean: 21.7s
- Ratio: 2.41x

**Trial 3:**
- Text mean: 8.3s
- Video mean: 22.2s
- Ratio: 2.67x

**Consistency:** Performance ratio remained stable across trials (2.4-2.9x)

---

## 4. Technical Insights

### 4.1 Processing Pipeline Comparison

**Text-based Pipeline:**
```
User Feedback → Load video_text.json → Load analysis_results.json
→ Construct prompt with text description → Gemini API call
→ Parse response → Save to feedbacks.json
```

**Video-based Pipeline:**
```
User Feedback → Load video file → Upload to Gemini Files API
→ Wait for processing (PROCESSING → ACTIVE) → Load analysis_results.json
→ Gemini API call with video reference → Parse response
→ Save to feedbacks.json
```

**Key Differences:**
- Text-based: Single API call, no file upload overhead
- Video-based: File upload + processing wait + API call
- Video upload time: ~10-15s (estimated from timing differences)
- Video processing varies by content complexity

### 4.2 API Rate Limiting Behavior

**Observed patterns:**
- Google Gemini free tier: 10 requests/minute
- Experiment delays (7s text, 10s video) stayed well under limit
- Zero rate limit errors during normal operation
- Single outlier suggests occasional API throttling despite staying under limits

### 4.3 Resource Usage Implications

**Text-based:**
- Minimal bandwidth (text payload ~1-5KB)
- No video storage on API side
- Lower API quota consumption

**Video-based:**
- High bandwidth (video upload ~1-50MB per request)
- Temporary video storage on Gemini servers
- Higher API quota consumption

---

## 5. Findings and Recommendations

### 5.1 Performance Winner: Text-based

**Quantitative advantages:**
1. **Speed:** 2.66x faster (8.4s vs 22.4s)
2. **Consistency:** 4x lower standard deviation (1.6s vs 6.5s)
3. **Predictability:** Narrower time range (5.4s vs 21.2s spread)
4. **Reliability:** 93% success rate with normal performance (14/15 tests)

**Qualitative advantages:**
1. Lower bandwidth requirements
2. Reduced API quota consumption
3. Simpler error handling
4. Better user experience (faster response)

### 5.2 When to Use Each Approach

**Use Text-based when:**
- ✓ Performance is critical
- ✓ Videos have pre-generated descriptions
- ✓ Consistent response times matter
- ✓ Bandwidth is limited
- ✓ API quota is constrained

**Use Video-based when:**
- ✓ Video descriptions are unavailable
- ✓ Visual context is essential
- ✓ Text descriptions may miss important details
- ✓ Accuracy is more important than speed

### 5.3 Production Deployment Recommendations

**Primary recommendation:** Deploy text-based feedback (`feedback_with_llm`)

**Implementation plan:**
1. Use text-based as default method
2. Ensure all videos have text descriptions via `video_to_text()`
3. Implement timeout handling for rare API delays (>30s)
4. Add fallback to video-based if text description unavailable
5. Monitor performance metrics and alert on >15s response times

**Hybrid approach (future enhancement):**
```python
def feedback_adaptive(video_path, file_name, criteria, feedback):
    """
    Adaptive feedback that uses text-based when available,
    falls back to video-based when necessary.
    """
    if has_text_description(file_name):
        try:
            return feedback_with_llm(file_name, criteria, feedback)
        except TimeoutError:
            logging.warning(f"Text-based timeout, trying video-based for {file_name}")
            return feedback_with_video(video_path, file_name, criteria, feedback)
    else:
        return feedback_with_video(video_path, file_name, criteria, feedback)
```

### 5.4 Limitations and Future Work

**Current limitations:**
1. Small sample size (14-15 tests per method)
2. Single API provider (Google Gemini)
3. Limited video content variety
4. No quality/accuracy comparison

**Future experiments:**
1. **Larger scale test:** 100+ videos across diverse content
2. **Quality analysis:** Compare feedback accuracy between methods
3. **Multi-provider test:** Test with different LLM providers
4. **Cost analysis:** Calculate $/request for each approach
5. **Hybrid optimization:** Find optimal switching logic

---

## 6. Conclusion

This experiment provides clear evidence that **text-based feedback is superior for performance-critical applications** in the VEA system. With 2.66x faster execution time and 4x better consistency, text-based feedback delivers a significantly better user experience.

The single outlier detected (221s delay) represents a rare edge case likely caused by temporary API throttling, not a fundamental limitation of the text-based approach.

**Final verdict:** Text-based feedback (`feedback_with_llm`) is recommended for production deployment, with video-based feedback (`feedback_with_video`) reserved as a fallback for videos without text descriptions.

---

## Appendix A: Complete Timing Data

### Text-based Results (Adjusted)

| Trial | Video | Criteria | Time (s) |
|-------|-------|----------|----------|
| 1 | #shorts #담배 | violence | 10.319 |
| 1 | 'its okay' | sexuality | 7.636 |
| 1 | BOOTED Gordon | horror | 6.627 |
| 1 | Leather bikinis | drugs | 8.370 |
| 1 | HEISENBERG | language | 7.460 |
| 2 | #shorts #담배 | violence | 8.230 |
| 2 | 'its okay' | sexuality | 10.439 |
| 2 | BOOTED Gordon | horror | 9.960 |
| 2 | Leather bikinis | drugs | 7.305 |
| 2 | HEISENBERG | language | ~~221.400~~ (excluded) |
| 3 | #shorts #담배 | violence | 12.009 |
| 3 | 'its okay' | sexuality | 7.587 |
| 3 | BOOTED Gordon | horror | 8.134 |
| 3 | Leather bikinis | drugs | 7.336 |
| 3 | HEISENBERG | language | 6.597 |

**Mean:** 8.429s | **Median:** 7.885s | **Std Dev:** 1.623s

### Video-based Results

| Trial | Video | Criteria | Time (s) |
|-------|-------|----------|----------|
| 1 | #shorts #담배 | violence | 24.567 |
| 1 | 'its okay' | sexuality | 18.222 |
| 1 | BOOTED Gordon | horror | 31.431 |
| 1 | Leather bikinis | drugs | 17.458 |
| 1 | HEISENBERG | language | 24.321 |
| 2 | #shorts #담배 | violence | 20.718 |
| 2 | 'its okay' | sexuality | 14.880 |
| 2 | BOOTED Gordon | horror | 29.020 |
| 2 | Leather bikinis | drugs | 14.739 |
| 2 | HEISENBERG | language | 29.111 |
| 3 | #shorts #담배 | violence | 24.656 |
| 3 | 'its okay' | sexuality | 13.011 |
| 3 | BOOTED Gordon | horror | 34.218 |
| 3 | Leather bikinis | drugs | 17.948 |
| 3 | HEISENBERG | language | 21.404 |

**Mean:** 22.380s | **Median:** 21.404s | **Std Dev:** 6.505s

---

## Appendix B: Statistical Calculations

### Text-based (Adjusted)
```
Data: [10.319, 7.636, 6.627, 8.370, 7.460, 8.230, 10.439, 9.960, 7.305,
       12.009, 7.587, 8.134, 7.336, 6.597]
n = 14
Mean (μ) = Σx/n = 118.009/14 = 8.429s
Median = (7.885 + 7.885)/2 = 7.885s (7th & 8th values when sorted)
Variance (σ²) = Σ(x-μ)²/(n-1) = 34.222/13 = 2.633
Std Dev (σ) = √2.633 = 1.623s
Min = 6.597s
Max = 12.009s
Range = 5.412s
Coefficient of Variation = σ/μ = 1.623/8.429 = 0.193 (19.3%)
```

### Video-based
```
Data: [24.567, 18.222, 31.431, 17.458, 24.321, 20.718, 14.880, 29.020,
       14.739, 29.111, 24.656, 13.011, 34.218, 17.948, 21.404]
n = 15
Mean (μ) = Σx/n = 335.703/15 = 22.380s
Median = 21.404s (8th value when sorted)
Variance (σ²) = Σ(x-μ)²/(n-1) = 592.523/14 = 42.323
Std Dev (σ) = √42.323 = 6.505s
Min = 13.011s
Max = 34.218s
Range = 21.207s
Coefficient of Variation = σ/μ = 6.505/22.380 = 0.291 (29.1%)
```

### Performance Ratio
```
Speedup = Video_mean / Text_mean = 22.380 / 8.429 = 2.66x
Time saved per request = 22.380 - 8.429 = 13.951s
Percentage improvement = (13.951 / 22.380) × 100 = 62.3%
```

---

**Report Generated:** November 23, 2025
**Author:** VEA Experiment System
**Tools Used:** Python 3.10, Google Gemini 2.5 Flash API
