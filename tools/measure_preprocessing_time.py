#!/usr/bin/env python3
"""
Measure the time it takes to generate video descriptions (preprocessing step)
This does NOT save results - only measures timing for fair comparison
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from google import genai
from api.utils import load_environment, ensure_env

def measure_description_generation_time(video_path: str) -> tuple[float, bool]:
    """
    Measure time to generate a video description
    Returns: (elapsed_time, success)
    """
    start_time = time.perf_counter()

    try:
        client = genai.Client()

        # Upload video
        file = client.files.upload(file=video_path)

        # Wait for processing
        while file.state.name == "PROCESSING":
            time.sleep(1.0)
            file = client.files.get(name=file.name)

        if file.state.name != "ACTIVE":
            return time.perf_counter() - start_time, False

        # Generate description (using the video analysis prompt)
        prompt = """이 영상의 내용을 자세히 묘사해주세요.

다음 형식으로 작성하세요:
- 시간대별로 구분 (예: 00:00, 00:02, 00:04...)
- 화면에 보이는 모든 것을 상세히 설명
- 들리는 소리나 대사를 정확히 기록
- 화면에 나타나는 텍스트나 자막도 포함
- 등장인물의 행동, 표정, 감정 묘사

영상을 정확히 분석하고, 모든 중요한 순간을 놓치지 않도록 세밀하게 작성해주세요."""

        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[file, prompt]
        )

        elapsed = time.perf_counter() - start_time

        # Check if we got a response
        if hasattr(resp, "text") and resp.text:
            return elapsed, True
        else:
            return elapsed, False

    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(f"Error: {e}")
        return elapsed, False

def main():
    load_environment()
    ensure_env("GOOGLE_API_KEY")

    video_dir = Path(__file__).parent / "yt_shorts"
    video_files = sorted(list(video_dir.glob("*.mp4")))[:20]  # Test with all 20 videos

    print("="*60)
    print("MEASURING PREPROCESSING TIME")
    print("="*60)
    print(f"\nTesting {len(video_files)} videos to measure description generation time...")
    print()

    times = []

    for i, video_file in enumerate(video_files, 1):
        print(f"[{i}/{len(video_files)}] Processing: {video_file.name[:50]}...")
        elapsed, success = measure_description_generation_time(str(video_file))

        if success:
            times.append(elapsed)
            print(f"  ✓ Completed in {elapsed:.2f}s")
        else:
            print(f"  ✗ Failed after {elapsed:.2f}s")

        # Delay between calls
        if i < len(video_files):
            print("  Waiting 3 seconds...")
            time.sleep(3)
        print()

    if times:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print("="*60)
        print("RESULTS")
        print("="*60)
        print(f"\nSuccessful measurements: {len(times)}/{len(video_files)}")
        print(f"Average preprocessing time: {avg_time:.2f}s")
        print(f"Min: {min_time:.2f}s")
        print(f"Max: {max_time:.2f}s")
        print()
        print("="*60)
        print("FAIR COMPARISON (including preprocessing)")
        print("="*60)
        print(f"\nText-based total per video: {avg_time:.2f}s (preprocessing) + 12.08s (moderation) = {avg_time + 12.08:.2f}s")
        print(f"Video-based total per video: 26.82s (direct moderation)")
        print()
        if avg_time + 12.08 < 26.82:
            speedup = 26.82 / (avg_time + 12.08)
            print(f"Text-based is still {speedup:.2f}x faster (including preprocessing)")
        else:
            slowdown = (avg_time + 12.08) / 26.82
            print(f"Text-based is {slowdown:.2f}x slower (when including preprocessing)")
    else:
        print("No successful measurements!")

if __name__ == "__main__":
    main()
