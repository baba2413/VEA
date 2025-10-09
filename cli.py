import argparse
import os
import sys

from api.utils import load_environment, ensure_env, extract_audio_from_video, has_ffmpeg
from api.gemini_test import analyze_video_with_gemini
from api.openai_vision import analyze_video_with_openai
from api.openai_audio import transcribe_audio_with_openai


def main():
    load_environment()

    parser = argparse.ArgumentParser(description="LLM Video/Audio capability probe")
    parser.add_argument("--video", type=str, default=None, help="Path to video file")
    parser.add_argument("--audio", type=str, default=None, help="Path to audio file")
    parser.add_argument("--gemini", action="store_true", help="Run Gemini video analysis")
    parser.add_argument("--openai-vision", action="store_true", help="Run OpenAI vision on sampled frames")
    parser.add_argument("--openai-audio", action="store_true", help="Run OpenAI audio transcription")
    parser.add_argument("--all", action="store_true", help="Run all available tests for provided inputs")
    parser.add_argument("--num-frames", type=int, default=8, help="Number of frames to sample for OpenAI vision")
    parser.add_argument("--gemini-model", type=str, default="gemini-2.0-flash-exp", help="Gemini model name")
    parser.add_argument("--openai-vision-model", type=str, default="gpt-4o-mini", help="OpenAI vision-capable model")
    parser.add_argument("--openai-asr-model", type=str, default="gpt-4o-mini-transcribe", help="OpenAI ASR model (or whisper-1)")
    args = parser.parse_args()

    if not any([args.gemini, args.openai_vision, args.openai_audio, args.all]):
        parser.error("Select at least one test flag: --gemini, --openai-vision, --openai-audio, or --all")

    if args.gemini or args.all:
        if not args.video:
            print("[Gemini] --video is required", file=sys.stderr)
        else:
            ensure_env("GOOGLE_API_KEY")
            try:
                out = analyze_video_with_gemini(args.video, model=args.gemini_model)
                print("\n=== Gemini Video Analysis ===\n")
                print(out)
            except Exception as e:
                print(f"[Gemini] Error: {e}", file=sys.stderr)

    if args.openai_vision or args.all:
        if not args.video:
            print("[OpenAI Vision] --video is required", file=sys.stderr)
        else:
            ensure_env("OPENAI_API_KEY")
            try:
                out = analyze_video_with_openai(
                    args.video,
                    num_frames=args.num_frames,
                    model=args.openai_vision_model,
                )
                print("\n=== OpenAI Vision (sampled frames) ===\n")
                print(out)
            except Exception as e:
                print(f"[OpenAI Vision] Error: {e}", file=sys.stderr)

    if args.openai_audio or args.all:
        ensure_env("OPENAI_API_KEY")
        audio_path = args.audio
        cleanup = False
        if not audio_path and args.video and has_ffmpeg():
            audio_path = extract_audio_from_video(args.video)
            cleanup = audio_path is not None
        if not audio_path:
            print("[OpenAI Audio] Provide --audio or --video with FFmpeg installed", file=sys.stderr)
        else:
            try:
                out = transcribe_audio_with_openai(audio_path, model=args.openai_asr_model)
                print("\n=== OpenAI Audio Transcription ===\n")
                print(out)
            except Exception as e:
                print(f"[OpenAI Audio] Error: {e}", file=sys.stderr)
            finally:
                if cleanup and audio_path and os.path.exists(audio_path):
                    try:
                        os.remove(audio_path)
                    except OSError:
                        pass


if __name__ == "__main__":
    main()


