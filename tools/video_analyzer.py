#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
유튜브 링크가 들어있는 JSON 파일을 읽어서:
1. 각 영상을 다운로드
2. Gemini API로 내용 분석
3. 결과를 JSON으로 저장

입력 JSON 형식:
[
    {
        "url": "https://www.youtube.com/watch?v=...",
        "tag": "주제",
        "remarks": "중요함"
    },
    ...
]

출력 JSON 형식:
[
    {
        "url": "https://www.youtube.com/watch?v=...",
        "gemini_response": "분석 결과...",
        "remarks": "중요함"
    },
    ...
]

사용 예:
  python video_analyzer.py input.json --output results.json
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yt_dlp as ytdlp
except ImportError:
    raise SystemExit("yt-dlp가 필요합니다. 먼저 `pip install yt-dlp` 를 실행하세요.")

# Import Gemini analyzer from api module
sys.path.insert(0, str(Path(__file__).parent.parent))
from api.utils import load_environment, ensure_env
from api.gemini_test import analyze_video_with_gemini


def load_input_json(json_path: Path) -> List[Dict]:
    """입력 JSON 파일을 로드합니다."""
    if not json_path.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {json_path}")
    
    data = json.loads(json_path.read_text(encoding="utf-8"))
    
    if not isinstance(data, list):
        raise ValueError("JSON 루트는 리스트여야 합니다.")
    
    # Validate structure
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"항목 {idx}는 객체여야 합니다.")
        if "url" not in item:
            raise ValueError(f"항목 {idx}에 'url' 필드가 없습니다.")
    
    return data


def download_video(url: str, outdir: Path, skip_existing: bool = True) -> Optional[Path]:
    """
    유튜브 영상을 다운로드하고 저장된 파일 경로를 반환합니다.
    
    Args:
        url: 유튜브 URL
        outdir: 다운로드 폴더
        skip_existing: 이미 존재하는 파일 건너뛰기
    
    Returns:
        다운로드된 파일 경로 (실패 시 None)
    """
    outdir.mkdir(parents=True, exist_ok=True)
    
    # 파일명 템플릿
    template = str(outdir / "%(title)s-%(id)s.%(ext)s")
    
    # "format": "bestvideo[height<=480]+bestaudio/best[height<=480]" 480p
    ydl_opts = {
        "format": "worst",
        "outtmpl": {"default": template},
        "noprogress": False,
        "ignoreerrors": False,
        "retries": 5,
        "quiet": False,
        "no_warnings": False,
        "postprocessors": [
            {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
        ],
        "overwrites": not skip_existing,
    }
    
    try:
        with ytdlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info to get the filename
            info = ydl.extract_info(url, download=True)
            if info is None:
                return None
            
            # Get the downloaded filename
            filename = ydl.prepare_filename(info)
            # Check if remuxed to mp4
            filepath = Path(filename)
            if not filepath.exists():
                # Try with .mp4 extension
                filepath = filepath.with_suffix(".mp4")
            
            if filepath.exists():
                return filepath
            else:
                print(f"경고: 다운로드 완료되었으나 파일을 찾을 수 없습니다: {filename}")
                return None
                
    except Exception as e:
        print(f"다운로드 실패: {url} -> {e}")
        return None


def process_video(item: Dict, temp_dir: Path) -> Dict:
    """
    단일 영상을 처리합니다: 다운로드 + Gemini 분석
    
    Args:
        item: 입력 JSON 항목 (url, tag, remarks 포함)
        temp_dir: 임시 다운로드 폴더
    
    Returns:
        출력 JSON 항목 (url, gemini_response, remarks 포함)
    """
    url = item["url"]
    print(f"\n{'='*60}")
    print(f"처리 중: {url}")
    print(f"{'='*60}")
    
    # 1. 영상 다운로드
    print("1. 영상 다운로드 중...")
    video_path = download_video(url, temp_dir)
    
    if video_path is None:
        return {
            "url": url,
            "gemini_response": "ERROR: 영상 다운로드 실패",
            "remarks": item.get("remarks", "")
        }
    
    print(f"   다운로드 완료: {video_path}")
    
    # 2. Gemini로 분석
    print("2. Gemini API로 영상 분석 중...")
    try:
        gemini_response = analyze_video_with_gemini(str(video_path))
        print("   분석 완료")
    except Exception as e:
        print(f"   분석 실패: {e}")
        gemini_response = f"ERROR: Gemini 분석 실패 - {str(e)}"
    
    # 3. 결과 생성
    result = {
        "url": url,
        "gemini_response": gemini_response,
        "remarks": item.get("remarks", "")
    }
    
    return result


def save_results_to_file(results: List[Dict], output_path: Path):
    """결과를 JSON 파일에 저장합니다."""
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def load_existing_results(output_path: Path) -> List[Dict]:
    """기존 결과 파일이 있으면 로드합니다."""
    if output_path.exists():
        try:
            data = json.loads(output_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                print(f"기존 결과 파일 발견: {len(data)}개 항목 로드됨")
                return data
        except Exception as e:
            print(f"기존 결과 파일 로드 실패: {e}")
    return []


def main():

    load_environment()
    ensure_env("GOOGLE_API_KEY")

    parser = argparse.ArgumentParser(
        description="유튜브 영상을 다운로드하고 Gemini API로 내용 분석"
    )
    parser.add_argument(
        "input_json",
        help="입력 JSON 파일 경로 (url, tag, remarks 포함된 리스트)"
    )
    parser.add_argument(
        "--output",
        default="analysis_results.json",
        help="출력 JSON 파일 경로 (기본: analysis_results.json)"
    )
    parser.add_argument(
        "--temp-dir",
        default="temp_videos",
        help="임시 다운로드 폴더 (기본: temp_videos)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=4.0,
        help="각 영상 처리 사이 대기 시간(초) (기본: 4.0)"
    )
    
    args = parser.parse_args()
    
    # 입력 로드
    input_path = Path(args.input_json)
    print(f"입력 파일 로딩: {input_path}")
    items = load_input_json(input_path)
    print(f"총 {len(items)}개 영상을 처리합니다.\n")
    
    # 출력 파일 준비 - 기존 결과 로드
    output_path = Path(args.output)
    results = load_existing_results(output_path)
    
    # 임시 폴더 준비
    # temp_dir = Path(args.temp_dir)
    # temp_dir.mkdir(parents=True, exist_ok=True)
    script_dir = Path(__file__).parent
    temp_dir = script_dir / "yt_shorts"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # 각 영상 처리
    for idx, item in enumerate(items, 1):
        print(f"\n[{idx}/{len(items)}]")
        result = process_video(item, temp_dir)
        results.append(result)
        
        # 실시간으로 결과 저장
        print(f"결과 저장 중... (현재 {len(results)}개 항목)")
        save_results_to_file(results, output_path)
        print(f"✓ {output_path}에 저장 완료")
        
        # 다음 처리 전 대기 (API rate limit 고려)
        if idx < len(items) and args.delay > 0:
            print(f"대기 중... ({args.delay}초)")
            time.sleep(args.delay)
    
    # 최종 완료 메시지
    print(f"\n{'='*60}")
    print(f"모든 작업 완료! 총 {len(results)}개 항목이 {output_path}에 저장되었습니다.")
    print(f"{'='*60}")
    
if __name__ == "__main__":
    main()

