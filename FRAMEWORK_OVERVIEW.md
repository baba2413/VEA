# VEA Framework Overview

A simplified explanation of how the Video Evaluation & Analysis system works.

---

## Section 1: Initial Video Input & Initial Analysis

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INITIAL ANALYSIS STAGE                               │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │              │
    │    VIDEO     │
    │    INPUT     │
    │              │
    └──────┬───────┘
           │
           │  Step 1: Convert to Text
           ▼
    ┌─────────────────────────────┐
    │      VIDEO → TEXT           │
    │                             │
    │  Gemini watches the video   │
    │  and generates a detailed   │
    │  text description           │
    └─────────────┬───────────────┘
                  │
                  │  Cache for reuse
                  ▼
    ┌─────────────────────────────┐
    │      VIDEO_TEXT.JSON        │
    │                             │
    │  Stored text descriptions   │
    │  of all analyzed videos     │
    └─────────────┬───────────────┘
                  │
                  │  Step 2: Analyze Text
                  ▼
    ┌─────────────────────────────┐
    │      TEXT + PROMPT          │
    │                             │
    │  Text Description           │
    │  +                          │
    │  Evaluation Criteria        │
    │  (from prompts.json)        │
    └─────────────┬───────────────┘
                  │
                  │  Gemini evaluates
                  ▼
    ┌─────────────────────────────┐
    │      ANALYSIS RESULTS       │
    ├─────────────────────────────┤
    │  • Violence:    O / X       │
    │  • Sexuality:   O / X       │
    │  • Horror:      O / X       │
    │  • Drugs:       O / X       │
    │  • Language:    O / X       │
    │                             │
    │  + Detailed Explanation     │
    └─────────────────────────────┘
```

### What happens:
1. **Video Upload** → User uploads a video file
2. **Video to Text** → Gemini watches the video and generates a detailed text description
3. **Cache Text** → Text description stored in `video_text.json` for efficient reuse
4. **Text Analysis** → Text description + evaluation criteria sent to Gemini
5. **Results Output** → Binary O/X decision for each criteria + detailed explanation

### Why two-stage process?
- **Efficiency**: Text descriptions can be reused for re-analysis without re-processing video
- **Speed**: Text-based analysis is faster than video analysis
- **Consistency**: Same text description ensures consistent re-analysis results


---

## Section 2: Feedback → Consideration → New Prompt

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FEEDBACK & IMPROVEMENT CYCLE                         │
└─────────────────────────────────────────────────────────────────────────────┘


         ┌──────────────────┐
         │  USER FEEDBACK   │
         │                  │
         │  "This analysis  │
         │   is wrong..."   │
         └────────┬─────────┘
                  │
                  ▼
    ┌─────────────────────────────┐
    │    FEEDBACK PROCESSING      │
    │                             │
    │  Gemini refines feedback    │
    │  considering video context  │
    └─────────────┬───────────────┘
                  │
                  ▼
    ┌─────────────────────────────┐
    │      FEEDBACKS.JSON         │
    │                             │
    │  Accumulated feedback       │
    │  per criteria               │
    └─────────────┬───────────────┘
                  │
                  │  Summarize into guideline
                  ▼
    ╔═════════════════════════════╗
    ║     CONSIDERATIONS.JSON     ║
    ║                             ║
    ║  Concise guidelines that    ║
    ║  modify evaluation criteria ║
    ║                             ║
    ║  Example:                   ║
    ║  "violence applies only     ║
    ║   to direct physical        ║
    ║   attacks, not cartoon..."  ║
    ╚═════════════╦═══════════════╝
                  │
                  │  Inject into prompt
                  ▼
    ┌─────────────────────────────────────────────────┐
    │               NEW PROMPT GENERATION             │
    │                                                 │
    │  ┌─────────────────────────────────────────┐   │
    │  │  BASE PROMPT (evaluation criteria)      │   │
    │  │  +                                      │   │
    │  │  CONSIDERATION (learned guidelines)     │   │
    │  │  =                                      │   │
    │  │  ENHANCED PROMPT                        │   │
    │  └─────────────────────────────────────────┘   │
    └─────────────────────┬───────────────────────────┘
                          │
                          ▼
    ┌─────────────────────────────────────────────────┐
    │                 RE-ANALYSIS                     │
    │                                                 │
    │    All videos re-analyzed with improved prompt  │
    │    → More accurate results based on feedback    │
    └─────────────────────────────────────────────────┘
```

### What happens:
1. **Write Feedback** → User provides correction when analysis is wrong
2. **Process Feedback** → AI refines the feedback with video context
3. **Accumulate** → Feedback stored in `feedbacks.json`
4. **Summarize** → All feedback summarized into `considerations.json`
5. **New Prompt** → Consideration injected into base prompt
6. **Re-analyze** → All videos re-evaluated with improved criteria


---

## Complete System Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              COMPLETE CYCLE                                  │
└─────────────────────────────────────────────────────────────────────────────┘

              SECTION 1                           SECTION 2
         ┌───────────────────┐            ┌───────────────────────────┐
         │                   │            │                           │
         │   VIDEO INPUT     │            │     USER FEEDBACK         │
         │        ↓          │            │           ↓               │
         │   VIDEO → TEXT    │            │     PROCESS FEEDBACK      │
         │        ↓          │            │           ↓               │
         │   VIDEO_TEXT.JSON │            │     FEEDBACKS.JSON        │
         │        ↓          │            │           ↓               │
         │   TEXT + PROMPT   │            │     CONSIDERATIONS.JSON   │
         │        ↓          │            │           ↓               │
         │   RESULTS (O/X)   │───────────▶│     NEW PROMPT            │
         │                   │  Review    │           ↓               │
         └───────────────────┘  Results   │     RE-ANALYSIS           │
                  ▲                       │     (uses cached text)    │
                  │                       │                           │
                  └───────────────────────┴───────────────────────────┘
                            Improved Results
```

---

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Video Text Cache | `video_text.json` | Cached text descriptions of videos |
| Base Evaluation Criteria | `prompts.json` | Defines 5 criteria with scoring rubrics |
| Learned Guidelines | `considerations.json` | Accumulated insights from feedback |
| User Feedback | `feedbacks.json` | Raw feedback per criteria |
| Analysis Results | `analysis_results.json` | O/X decisions + explanations |

---

## The Learning Loop

```
    Initial Analysis
          │
          ▼
    ┌───────────┐     Wrong?     ┌───────────┐
    │  Results  │ ─────────────▶ │  Feedback │
    └───────────┘                └─────┬─────┘
          ▲                            │
          │                            ▼
          │                    ┌───────────────┐
          │                    │ Consideration │
          │                    └───────┬───────┘
          │                            │
          │      Better Prompt         │
          └────────────────────────────┘
```

The system continuously learns from user corrections, making evaluation more accurate over time.
