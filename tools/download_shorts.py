#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
유튜브(쇼츠 포함) 링크가 들어있는 JSON 파일을 읽어
모든 영상을 일괄 다운로드하는 스크립트.
- yt-dlp 사용 (pip install yt-dlp)
- JSON 형식:
  1) 단순 리스트: ["https://youtube.com/shorts/...", "https://youtu.be/..."]
  2) 객체 내부 키: {"videos": ["...","..."]}  (키 이름은 --json-key 옵션으로 지정 가능, 기본값: videos)
사용 예:
  python download_shorts.py yt_list.json --outdir downloads --workers 1 --format "worst"
"""

import argparse
import concurrent.futures as futures
import json
import re
from pathlib import Path
from typing import Iterable, List, Union

try:
    import yt_dlp as ytdlp
except ImportError:
    raise SystemExit("yt-dlp가 필요합니다. 먼저 `pip install yt-dlp` 를 실행하세요.")

SHORTS_RX = re.compile(r"(https?://)?(www\.)?(youtube\.com/shorts/[^?\s]+)")

def load_links(json_path: Union[str, Path], json_key: str = "videos") -> List[str]:
    p = Path(json_path)
    if not p.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    links: List[str] = []
    if isinstance(data, list):
        links = [str(x) for x in data]
    elif isinstance(data, dict):
        # 우선 지정 키를 시도
        if json_key in data and isinstance(data[json_key], list):
            links = [str(x) for x in data[json_key]]
        else:
            # dict 전체에서 URL로 보이는 값들을 추출(백업 전략)
            for v in data.values():
                if isinstance(v, list):
                    links.extend(str(x) for x in v if isinstance(x, str))
                elif isinstance(v, str):
                    links.append(v)
    else:
        raise ValueError("JSON 형식이 리스트나 객체여야 합니다.")

    # 간단 필터: http/https 포함, 유튜브 도메인만
    links = [u.strip() for u in links if isinstance(u, str) and ("youtube.com" in u or "youtu.be" in u)]
    # 중복 제거(순서 유지)
    seen = set()
    uniq = []
    for u in links:
        if u not in seen:
            uniq.append(u)
            seen.add(u)
    return uniq

def mk_ydl_opts(outdir: Union[str, Path], fmt: str, rate_limit: str, retries: int, skip_existing: bool, write_subs: bool):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    # 파일명 템플릿: 제목-영상ID.확장자
    template = str(outdir / "%(title)s-%(id)s.%(ext)s")
    opts = {
        "format": fmt,
        "outtmpl": {"default": template},
        "noprogress": False,
        "ignoreerrors": True,
        "retries": retries,
        "ratelimit": rate_limit if rate_limit else None,
        "concurrent_fragment_downloads": 4,  # HLS/DASH 세그먼트 동시 다운로드
        "quiet": False,
        "no_warnings": False,
        "writesubtitles": write_subs,
        "subtitleslangs": ["ko","en.*","ja","auto"],
        "postprocessors": [
            {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},  # 가급적 mp4로 정리
        ],
        "overwrites": not skip_existing,
    }
    # None 값 제거
    return {k: v for k, v in opts.items() if v is not None}

def download_one(url: str, ydl_opts) -> str:
    try:
        with ytdlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return f"OK  - {url}"
    except Exception as e:
        return f"FAIL- {url} -> {e}"

def chunked(iterable: Iterable[str], size: int):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch

def main():
    parser = argparse.ArgumentParser(description="YouTube/Shorts JSON 일괄 다운로드")
    parser.add_argument("json_path", help="유튜브 링크가 담긴 JSON 경로")
    parser.add_argument("--json-key", default="videos", help="객체 형식 JSON에서 링크 리스트가 들어있는 키 (기본: videos)")
    parser.add_argument("--outdir", default="downloads", help="저장 폴더 (기본: downloads)")
    parser.add_argument("--format", default="worst", help="yt-dlp 포맷 선택 (best: bestvideo+bestaudio/best)")
    parser.add_argument("--workers", type=int, default=4, help="동시 다운로드 작업 수 (기본: 4)")
    parser.add_argument("--rate-limit", default="", help="속도 제한 예: 2M, 500K (기본: 제한 없음)")
    parser.add_argument("--retries", type=int, default=5, help="실패 시 재시도 횟수 (기본: 5)")
    parser.add_argument("--skip-existing", action="store_true", help="이미 존재하는 파일은 건너뜀")
    parser.add_argument("--write-subs", action="store_true", help="가능하면 자막 파일도 저장")
    args = parser.parse_args()

    links = load_links(args.json_path, args.json_key)
    if not links:
        raise SystemExit("다운로드할 유튜브 링크를 찾지 못했습니다. JSON 내용을 확인해주세요.")

    ydl_opts = mk_ydl_opts(
        outdir=args.outdir,
        fmt=args.format,
        rate_limit=args.rate_limit,
        retries=args.retries,
        skip_existing=args.skip_existing,
        write_subs=args.write_subs,
    )

    print(f"총 {len(links)}개 링크 다운로드 시작... (workers={args.workers})")
    results: List[str] = []
    with futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        for res in ex.map(lambda u: download_one(u, ydl_opts), links):
            print(res)
            results.append(res)

    # 요약
    ok = sum(1 for r in results if r.startswith("OK"))
    fail = len(results) - ok
    print("="*60)
    print(f"완료: {ok} 성공, {fail} 실패")

if __name__ == "__main__":
    main()
