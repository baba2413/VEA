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
        "remarks": "중요함",
        "human_comments": "사람이 작성한 코멘트"
    },
    ...
]

출력 JSON 형식:
[
    {
        "url": "https://www.youtube.com/watch?v=...",
        "gemini_response": "분석 결과...",
        "remarks": "중요함",
        "human_comments": "사람이 작성한 코멘트"
    },
    ...
]

사용 예:
  python video_analyzer.py input.json --output results.json
"""

import argparse
import json
import re
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
            "tag": item.get("tag", ""),
            "gemini_response": "ERROR: 영상 다운로드 실패",
            "remarks": item.get("remarks", ""),
            "human_comments": item.get("human_comments", "")
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
        "tag": item.get("tag", ""),
        "gemini_response": gemini_response,
        "remarks": item.get("remarks", ""),
        "human_comments": item.get("human_comments", "")
    }
    
    return result


def build_prompt_for_tag(tag: str) -> str:
    tag_text = (tag or "").strip()
    prompts = {
        "폭력성": (
            """
            당신은 영상물 심의 전문가이며, 제공되는 영상에 대해 ‘폭력성’ 관련하여 검사한다.
            ‘폭력성’ 관련 기준은 다음과 같다.
            0점: 폭력성 없음. 물리적·언어적 폭력, 위협, 상해 장면이 전혀 없으며 폭력적 상황이나 암시도 없음. (예: 일상 대화, 코미디, 자연 다큐 등)
            1점: 간접적 또는 상징적 폭력. 경미한 신체적 충돌(밀기, 때리기 등) 또는 위협적 언행이 있으나 현실적 고통이나 공포감을 유발하지 않으며, 과장되거나 짧게 묘사됨. (예: 코믹한 다툼, 스포츠 경기 중 충돌, 만화적 폭력)
            2점: 현실적 폭력 묘사 존재. 구타, 싸움, 무기 사용 등 물리적 폭력 장면이 존재하나 잔혹하게 표현되지 않음. 피, 상처 등 시각적 표현이 있을 수 있으나 제한적. 감정적으로 불쾌하거나 충격적이지 않음. (예: 액션, 범죄 장면, 제한된 총격전)
            3점: 명확하고 지속적인 폭력 표현. 구타, 총격, 고문 등 반복적·직접적 폭력이 현실적으로 묘사됨. 피, 상처, 비명 등 시청자에게 강한 불쾌감이나 공포를 유발할 수 있음. (예: 범죄 스릴러, 전쟁 장면, 복수극의 격렬한 장면)
            반드시 출력 양식의 형태 그대로 출력한다.
            출력 양식은 다음과 같다:
            폭력성 점수: {0~3}점
            근거: {감지된 민감 요소 및 근거 서술}
            """
        ),
        "선정성": (
            """
            당신은 영상물 심의 전문가이며, 제공되는 영상에 대해 ‘선정성’ 관련하여 검사한다.
            ‘선정성’ 관련 기준은 다음과 같다.
            0점: 없거나 매우 약한 선정성. 성적 내용이나 신체 노출이 없거나 매우 약하다. 일상생활에서 흔히 접하는 애정표현 수준이다. (예: 포옹 등 일상적 표현)
            1점: 경미하고 간결한 선정성. 성적 맥락과 무관한 신체 노출이 간결히 표현됨. 성적인 신체 노출, 접촉, 소리, 이미지, 언어 등이 경미하게 표현됨. (예: 키스 등 가벼운 수준의 성적 접촉, 농담, 은유)
            2점: 선정적 요소가 있으나 지속적이고 구체적이지 않음. 신체 노출은 전체 맥락에 타당하게 표현됨. 성적인 신체 노출, 소리, 이미지, 언어가 자극적이지 않음. 성적 행위는 구체적이지 않을 것. 일반 사회 윤리에 어긋나는 성적 행위가 아닐 것. (예: 일반적 노출, 성적 암시)
            3점: 과도하며, 구체적이고 직접적, 노골적인 선정성. 신체노출이 직접적으로 노출되어 있으나 지속적이지는 않음. 성적행위가 구체적, 지속적, 노골적임. 성적인 소리, 이미지, 언어가 직접적이고 자극적임. 일반 사회 윤리를 어긋나는 성적 행위는 지나치지 않아야 함. (예: 구체적인 실제 성적 묘사)
            반드시 출력 양식의 형태 그대로 출력한다.
            출력 양식은 다음과 같다:
            선정성 점수: {0~3}점
            근거: {감지된 민감 요소 및 근거 서술}
            """
        ),
        "공포": (
            """
            당신은 영상물 심의 전문가이며, 제공되는 영상에 대해 ‘공포’ 관련하여 검사한다.
            ‘공포’ 관련 기준은 다음과 같다.
            0점: 공포 요소 없음. 공포감, 긴장감, 위협적 분위기 전혀 없음. (예: 일상 드라마, 코미디, 다큐멘터리 등)
            1점: 약한 긴장 또는 놀람. 순간적인 놀람 요소나 약한 긴장감은 있으나 불안감은 거의 없음. 직접적 위협이나 피·괴기 요소 없음. (예: 어린이 미스터리, 가벼운 스릴러, 약한 점프스케어)
            2점: 중간 정도의 공포. 어두운 분위기나 불안한 연출이 반복됨. 간접적인 공포 묘사(유령, 그림자, 비명 등)가 있음. (예: 청소년 관람가 호러, 심리적 스릴러)
            3점: 강한 공포와 시각적 충격. 피, 사체, 괴기한 존재 등이 자주 등장. 공포가 주요 소재이며 강한 긴장감 유발. (예: 슬래셔, 좀비물, 잔혹한 살인 장면)
            반드시 출력 양식의 형태 그대로 출력한다.	
            출력 양식은 다음과 같다:
            공포 점수: {0~3}점
            근거: {감지된 민감 요소 및 근거 서술}
            """
        ),
        "약물": (
            """
            당신은 영상물 심의 전문가이며, 제공되는 영상에 대해 ‘약물’ 관련하여 검사한다.
            ‘약물’ 관련 기준은 다음과 같다.
            0점: 마약 관련 내용 없음. 마약, 흡입, 거래, 중독 등의 언급이나 장면이 전혀 없음. (예: 일반 드라마, 코미디, 가족용 콘텐츠)
            1점: 간접 언급 또는 경미한 등장. 대사나 배경에서 마약이 잠깐 언급되지만 구체적 묘사 없음. 마약 사용이나 거래 장면 없음. (예: 사회문제 언급용 뉴스, 단편적 대화 속 언급)
            2점: 제한적 등장 / 비묘사적 사용 암시. 마약이 극 중 일부 소재로 등장하나, 사용 장면은 간접적으로 표현되거나 짧게 암시됨. 미화되지 않음. (예: 범죄 드라마, 스릴러)
            3점: 명확한 사용 및 거래 묘사. 인물이 마약을 사용하거나 거래하는 장면이 명확히 등장함. 중독, 환각 등 표현이 구체적임. 다만 미화는 없음. (예: 범죄 영화, 사회고발물, 실존사건 기반 작품)
            반드시 출력 양식의 형태 그대로 출력한다.
            출력 양식은 다음과 같다:
            약물 점수: {0~3}점
            근거: {감지된 민감 요소 및 근거 서술}
            """
        ),
        "언어": (
            """
            당신은 영상물 심의 전문가이며, 제공되는 영상에 대해 ‘언어’ 관련하여 검사한다.
            ‘언어’ 관련 기준은 다음과 같다.
            0점: 욕설, 비속어, 저속어 등이 없거나 매우 약함. 아동의 언어습관에 부정적 영향이 없다. 차별적, 인권침해적 언어 사용이 없다. (예: 바보)
            1점: 욕설, 비속어, 저속어가 경미하고 간결하다. 청소년의 언어 습관에 부정적 영향이 없다. 차별적, 인권침해적 언어가 경미하고 간결하다. 가족, 대인관계, 교육과정에서 통상 접할 수 있다. (예: 맥락에 맞는 욕설)
            2점: 욕설, 비속어, 저속어가 있으나 빈번하거나 자극적이지 않다. 사회 통념상 용인되는 수준에서 사용되며, 거친 표현은 맥락·내용 전개상 수용 가능하다. 언어 폭력 요소가 과도하지 않음. (예: 현실적 욕설)
            3점: 욕설, 비속어, 저속어가 반복적, 지속적으로 사용됨. 정서적·인격적 모욕감이나 수치심을 유발하는 수준의 욕설·비속어·저속어가 반복·지속적으로 사용됨. (예: 강한 욕설·모욕, 성적 비하)
            반드시 출력 양식의 형태 그대로 출력한다.
            출력 양식은 다음과 같다:
            언어 점수: {0~3}점.
            근거: {감지된 민감 요소 및 근거 서술}
            """
        ),
        "모방 위험성": (
            """
            당신은 영상물 심의 전문가이며, 제공되는 영상에 대해 ‘모방위험성’ 관련하여 검사한다.
            ‘모방위험성’ 관련 기준은 다음과 같다.
            0점: 모방 위험 행위 없음. 영상 내에 범죄, 폭력, 자해, 비행 등 모방할 수 있는 위험 행위가 전혀 묘사되지 않음. (예: 일상 드라마, 코미디, 인터뷰, 풍경 영상 등)
            1점: 낮음 (비현실적/간접적 묘사). 위험 행위가 묘사되나, 맥락상 비현실적이거나 매우 추상적/간접적이며 따라하기 어려움. (예: 판타지, 개그, 결과만 암시) (예: 과장된 만화적 폭력, 범죄 행위가 아닌 범죄의 결과만 보여주는 장면)
            2점: 중간 (부정적 결과 강조). 위법 행위(절도, 단순 폭력 등)가 묘사되지만 그 과정이 구체적이지 않음. 무엇보다 해당 행위로 인한 부정적 결과(예: 고통, 부상, 후회, 체포)가 명확히 강조되어 모방 심리를 억제함. (예: 학교 폭력의 가해자가 처벌받고 피해자가 고통스러워하는 장면, 범죄자가 결국 체포되는 서사물)
            3점: 높음 (구체적이거나 미화된 묘사). 위법 행위(범죄, 자해, 폭력)의 과정이 일부 구체적으로 묘사되거나, 행위가 매력적으로(쿨하게) 미화됨. 부정적 결과가 약하거나 약하게 표현되어 모방을 자극할 위험이 있음. (예: 주인공이 멋지게 범죄 성공, 자해를 낭만화하거나 문제 해결책처럼 묘사하는 장면)
            반드시 출력 양식의 형태 그대로 출력한다.
            출력 양식은 다음과 같다:
            모방위험성 점수: {0~3}점
            근거: {감지된 민감 요소 및 근거 서술}
            """
        ),
        "주제": (
            """
            - 이 항목은 0~4점 점수를 매기지 않고, 아래 예시와 같이 사회적/윤리적/역사적으로 민감한 내용이 감지되었는지 여부와 그 근거를 서술한다.
            - 감지된 내용이 없다면 "해당 사항 없음"으로 표기한다.
            - [주요 분석 대상 예시]
                - 사회/윤리적 문제: 소아성애, 가정폭력, 아동 학대, 자살/자해 조장, 인신매매 등 사회 통념에 어긋나거나 불법적인 행위를 묘사하거나 미화하는 내용
                - 차별 및 혐오: 인종, 민족, 국적, 성별, 종교, 지역, 장애, 성적 지향 등에 대한 노골적인 차별, 비하, 편견을 조장하는 표현
                - 역사적 논란: 나치즘, 파시즘, 일본 군국주의 등 특정 역사적 비극을 옹호하거나 왜곡하는 상징, 발언, 장면
            반드시 출력 양식 형태로 출력한다.
            출력 양식은 다음과 같다:
            주제 및 내용: [감지된 민감 주제 및 근거 서술. (예: "역사적 논란: 나치즘을 상징하는 문양이 00:00~00:00(분:초) 장면에 명확한 비판 없이 노출됨.") / 감지된 내용이 없을 경우 "해당 사항 없음"]
            """
        ),
    }

    # 지정되지 않은 태그는 일반 심의 지침의 간결 버전을 사용
    default_prompt = (
        """
        당신의 임무는 영상 등급 심의 전문가로서 주어진 영상의 내용을 간결하게 평가하는 것이다.
        다음 항목만 출력한다.

        [출력 형식]
        내용 요약: [영상 내용 핵심 요약]
        핵심 이슈: [해당 콘텐츠에서 가장 주의할 요소 1~2개]
        종합의견: [최종 판단]
        """
    )

    # 다중 태그(쉼표/세미콜론/슬래시/파이프 구분)와 동의어/공백 정규화를 지원
    parts: List[str] = []
    if tag_text:
        parts = [p.strip() for p in re.split(r"[,\|/;]+", tag_text) if p.strip()]

    # 공백 제거 버전으로 키를 매핑 (예: "모방위험성" -> "모방 위험성")
    normalized_key_to_key = {k.replace(" ", ""): k for k in prompts.keys()}

    # 동의어/별칭 매핑
    alias_to_key = {
        "모방위험성": "모방 위험성",
        "대사": "언어",
    }

    # 우선순위: 입력 순서대로 첫 매칭 프롬프트 사용
    for part in parts:
        # 1) 완전 일치
        if part in prompts:
            return prompts[part]

        norm = part.replace(" ", "")

        # 2) 공백 제거 후 일치 (예: "모방위험성")
        if norm in normalized_key_to_key:
            return prompts[normalized_key_to_key[norm]]

        # 3) 동의어 매핑 (예: "대사" -> "언어")
        if norm in alias_to_key:
            canonical = alias_to_key[norm]
            if canonical in prompts:
                return prompts[canonical]

    # 단일 태그이거나 어떤 항목도 매칭되지 않은 경우 기본 처리
    return prompts.get(tag_text, default_prompt)


def process_video_with_tag(item: Dict, temp_dir: Path) -> Dict:
    """입력 JSON 항목을 받아 태그별 프롬프트로 분석합니다."""
    url = item["url"]
    tag = item.get("tag", "")
    print(f"\n{'='*60}")
    print(f"태그 기반 처리 중: {url} (tag={tag})")
    print(f"{'='*60}")

    print("1. 영상 다운로드 중...")
    video_path = download_video(url, temp_dir)
    if video_path is None:
        return {
            "url": url,
            "tag": tag,
            "gemini_response": "ERROR: 영상 다운로드 실패",
            "remarks": item.get("remarks", ""),
            "human_comments": item.get("human_comments", ""),
        }

    prompt = build_prompt_for_tag(tag)
    print("2. Gemini API로 태그별 프롬프트 분석 중...")
    try:
        gemini_response = analyze_video_with_gemini(str(video_path), prompt=prompt)
        print("   분석 완료")
    except Exception as e:
        print(f"   분석 실패: {e}")
        gemini_response = f"ERROR: Gemini 분석 실패 - {str(e)}"

    return {
        "url": url,
        "tag": tag,
        "gemini_response": gemini_response,
        "remarks": item.get("remarks", ""),
        "human_comments": item.get("human_comments", ""),
    }


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
        help="입력 JSON 파일 경로 (url, tag, remarks, human_comments 포함된 리스트)"
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
        result = process_video_with_tag(item, temp_dir)
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

