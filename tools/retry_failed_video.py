#!/usr/bin/env python3
"""Retry preprocessing measurement for the failed video"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from google import genai
from api.utils import load_environment, ensure_env

def measure_description_generation_time(video_path: str) -> tuple[float, bool]:
    start_time = time.perf_counter()

    try:
        client = genai.Client()

        # Upload video
        print('Uploading video...')
        file = client.files.upload(file=video_path)

        # Wait for processing
        wait_count = 0
        while file.state.name == "PROCESSING":
            time.sleep(1.0)
            wait_count += 1
            if wait_count % 5 == 0:
                print(f'  Processing... {wait_count}s')
            file = client.files.get(name=file.name)

        print(f'Video state: {file.state.name}')

        if file.state.name != "ACTIVE":
            return time.perf_counter() - start_time, False

        # Generate description
        print('Generating description...')
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

        if hasattr(resp, "text") and resp.text:
            print(f'Description length: {len(resp.text)} chars')
            return elapsed, True
        else:
            return elapsed, False

    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(f"Error: {e}")
        return elapsed, False

if __name__ == "__main__":
    load_environment()
    ensure_env("GOOGLE_API_KEY")

    video_path = Path(__file__).parent / "yt_shorts" / "where's my daughter scene ｜ prisoners (2013)-nY3Nsri3NOA.mp4"

    print(f"Retrying failed video: {video_path.name}")
    print()

    elapsed, success = measure_description_generation_time(str(video_path))

    if success:
        print(f"\n✓ Success in {elapsed:.2f}s")
    else:
        print(f"\n✗ Failed after {elapsed:.2f}s")
