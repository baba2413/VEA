#!/usr/bin/env python3
"""
비디오 클리핑 도구
입력된 비디오 파일을 30초 단위로 클리핑하여 각각 저장합니다.
"""

import os
import sys
import subprocess
from pathlib import Path
import argparse

try:
    from moviepy.editor import VideoFileClip
except ImportError:
    try:
        from moviepy import VideoFileClip
    except ImportError:
        print("오류: moviepy 라이브러리를 찾을 수 없습니다.")
        print("다음 명령어로 설치해주세요: pip install moviepy")
        sys.exit(1)


def check_ffmpeg():
    """ffmpeg가 설치되어 있는지 확인합니다."""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_video_duration(video_path):
    """비디오 파일의 총 길이를 초 단위로 반환합니다."""
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration
        clip.close()
        return duration
    except Exception as e:
        print(f"비디오 파일을 읽는 중 오류가 발생했습니다: {e}")
        return None


def clip_video(input_path, output_dir, clip_duration=30):
    """
    비디오를 지정된 시간 단위로 클리핑합니다.
    
    Args:
        input_path (str): 입력 비디오 파일 경로
        output_dir (str): 출력 디렉토리 경로
        clip_duration (int): 클립 길이 (초 단위, 기본값: 30초)
    """
    # ffmpeg 설치 확인
    if not check_ffmpeg():
        print("오류: ffmpeg가 설치되어 있지 않습니다.")
        print("\nffmpeg 설치 방법:")
        print("  Windows: winget install ffmpeg")
        print("  Mac: brew install ffmpeg")
        print("  Linux: sudo apt install ffmpeg (Ubuntu/Debian)")
        return False
    
    # 입력 파일 존재 확인
    if not os.path.exists(input_path):
        print(f"오류: 입력 파일 '{input_path}'을 찾을 수 없습니다.")
        return False
    
    # 출력 디렉토리 생성
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 비디오 정보 가져오기
    print(f"비디오 파일 분석 중: {input_path}")
    total_duration = get_video_duration(input_path)
    
    if total_duration is None:
        return False
    
    print(f"비디오 총 길이: {total_duration:.2f}초")
    
    # 입력 파일명에서 확장자 제거
    base_name = Path(input_path).stem
    
    # 클립 개수 계산
    num_clips = int(total_duration // clip_duration) + (1 if total_duration % clip_duration > 0 else 0)
    print(f"총 {num_clips}개의 클립을 생성합니다.")
    
    try:
        for i in range(num_clips):
            start_time = i * clip_duration
            end_time = min((i + 1) * clip_duration, total_duration)
            duration = end_time - start_time
            
            # 출력 파일명 생성
            output_filename = f"{base_name}_clip_{i+1:03d}_{start_time:.0f}s-{end_time:.0f}s.mp4"
            output_file_path = output_path / output_filename
            
            print(f"클립 {i+1}/{num_clips} 생성 중: {output_filename}")
            
            # ffmpeg를 사용하여 클립 생성
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-ss', str(start_time),
                '-t', str(duration),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-avoid_negative_ts', 'make_zero',
                str(output_file_path),
                '-y',  # 덮어쓰기
                '-loglevel', 'error'  # 오류만 출력
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"저장 완료: {output_file_path}")
            else:
                print(f"오류 발생: {result.stderr}")
                return False
    
    except Exception as e:
        print(f"클리핑 중 오류가 발생했습니다: {e}")
        return False
    
    print(f"\n모든 클립이 성공적으로 생성되었습니다!")
    print(f"출력 디렉토리: {output_path.absolute()}")
    return True


def main():
    """메인 함수 - CLI 인터페이스"""
    parser = argparse.ArgumentParser(
        description="비디오를 30초 단위로 클리핑합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python video_clipper.py input_video.mp4
  python video_clipper.py input_video.mp4 -o ./clips
  python video_clipper.py input_video.mp4 -d 60 -o ./clips
        """
    )
    
    parser.add_argument(
        'input_video',
        help='클리핑할 비디오 파일 경로'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='./video_clips',
        help='출력 디렉토리 (기본값: ./video_clips)'
    )
    
    parser.add_argument(
        '-d', '--duration',
        type=int,
        default=30,
        help='클립 길이 (초 단위, 기본값: 30)'
    )
    
    args = parser.parse_args()
    
    # 입력 파일 경로 정규화
    input_path = Path(args.input_video).resolve()
    
    print("=" * 50)
    print("비디오 클리핑 도구")
    print("=" * 50)
    print(f"입력 파일: {input_path}")
    print(f"출력 디렉토리: {args.output}")
    print(f"클립 길이: {args.duration}초")
    print("=" * 50)
    
    # 클리핑 실행
    success = clip_video(
        str(input_path),
        args.output,
        args.duration
    )
    
    if success:
        print("\n✅ 클리핑이 성공적으로 완료되었습니다!")
        sys.exit(0)
    else:
        print("\n❌ 클리핑 중 오류가 발생했습니다.")
        sys.exit(1)


if __name__ == "__main__":
    main()
