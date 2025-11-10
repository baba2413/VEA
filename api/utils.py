import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
import ast

import cv2
import numpy as np
from dotenv import load_dotenv


def load_environment() -> None:
    """Load environment variables from a local .env file if present."""
    load_dotenv(override=False)


def ensure_env(*keys: str) -> None:
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def sample_video_frames(video_path: str, num_frames: int) -> List[np.ndarray]:
    if num_frames <= 0:
        raise ValueError("num_frames must be > 0")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        # Fallback: try iterating until break
        frames = []
        ok = True
        while ok:
            ok, frame = cap.read()
            if ok:
                frames.append(frame)
        cap.release()
        if not frames:
            raise RuntimeError("Could not read any frames from the video")
        if len(frames) <= num_frames:
            return frames
        # Evenly sample indexes
        idxs = np.linspace(0, len(frames) - 1, num_frames, dtype=int).tolist()
        return [frames[i] for i in idxs]

    # Evenly spaced frames across the whole video
    idxs = np.linspace(0, total_frames - 1, num_frames, dtype=int).tolist()
    sampled: List[np.ndarray] = []
    for idx in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if ok and frame is not None:
            sampled.append(frame)
    cap.release()

    if not sampled:
        raise RuntimeError("Failed to sample frames from the video")
    return sampled


def encode_frame_to_data_url(frame_bgr: np.ndarray, quality: int = 85) -> str:
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(max(1, min(100, quality)))]
    ok, buf = cv2.imencode(".jpg", frame_bgr, encode_params)
    if not ok:
        raise RuntimeError("Failed to encode frame to JPEG")
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def extract_audio_from_video(video_path: str, out_ext: str = ".mp3") -> Optional[str]:
    if not has_ffmpeg():
        return None
    fd, out_path = tempfile.mkstemp(suffix=out_ext)
    os.close(fd)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        "libmp3lame" if out_ext.lower() == ".mp3" else "pcm_s16le",
        out_path,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return out_path
    except subprocess.CalledProcessError:
        try:
            os.remove(out_path)
        except OSError:
            pass
        return None


def parse_gemini_analysis(response_text: str) -> Dict[str, Any]:
    """Parse Gemini's structured Korean analysis response.

    Expected format:
    내용 요약: [summary]

    1. 주제 및 내용: [점수(0~4)], [description]
    2. 선정성: ...
    3. 폭력성: ...
    4. 공포: ...
    5. 약물: ...
    6. 언어: ...
    7. 모방 위험성: ...

    - 종합의견: [overall opinion]

    Returns a structured dict with scores, details, summary, and overall_opinion.
    """
    result: Dict[str, Any] = {
        "content_summary": "",
        "scores": {},
        "details": {},
        "overall_opinion": "",
        "raw_text": response_text
    }

    # Extract content summary
    summary_match = re.search(r'내용 요약:\s*(.+?)(?=\n\d+\.|\n-|\Z)', response_text, re.DOTALL)
    if summary_match:
        result["content_summary"] = summary_match.group(1).strip()

    # Define category mapping (Korean name -> English key)
    categories = {
        "주제 및 내용": "topic",
        "주제": "topic",
        "선정성": "sexuality",
        "폭력성": "violence",
        "공포": "horror",
        "약물": "drugs",
        "언어": "language",
        "모방 위험성": "imitable",
        "모방위험성": "imitable"
    }

    # Extract scores and details for each category
    for korean_name, eng_key in categories.items():
        # Pattern: "N. 카테고리명: [점수(0~4)] or 점수(숫자), 설명"
        pattern = rf'\d+\.\s*{re.escape(korean_name)}:\s*(?:\[)?점?수?\(?(\d+)\)?(?:\])?[,\s]+(.+?)(?=\n\d+\.|\n-|\Z)'
        match = re.search(pattern, response_text, re.DOTALL)

        if match:
            score_str = match.group(1)
            description = match.group(2).strip()

            try:
                score = int(score_str)
                result["scores"][eng_key] = max(0, min(4, score))  # Clamp to 0-4
            except (ValueError, TypeError):
                result["scores"][eng_key] = 0

            result["details"][eng_key] = description

    # Extract overall opinion
    opinion_match = re.search(r'-?\s*종합\s*의견:\s*(.+?)(?=\n\n|\Z)', response_text, re.DOTALL)
    if opinion_match:
        result["overall_opinion"] = opinion_match.group(1).strip()

    return result


def get_results_file_path() -> str:
    """Get the path to the analysis results JSON file."""
    api_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(api_dir, "analysis_results.json")


def load_analysis_results() -> Dict[str, Any]:
    """Load all analysis results from JSON file."""
    results_path = get_results_file_path()
    if not os.path.exists(results_path):
        return {}

    try:
        with open(results_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_analysis_result(filename: str, analysis_data: Dict[str, Any]) -> None:
    """Save analysis result for a specific video file."""
    results = load_analysis_results()

    # Add timestamp
    analysis_data["analyzed_at"] = datetime.utcnow().isoformat() + "Z"
    analysis_data["video_filename"] = filename

    results[filename] = analysis_data

    results_path = get_results_file_path()
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def get_analysis_result(filename: str) -> Optional[Dict[str, Any]]:
    """Get analysis result for a specific video file."""
    results = load_analysis_results()
    return results.get(filename)


def load_category_prompts(file_path: Optional[str] = None) -> Dict[str, str]:
    """
    Load category-specific prompts from a local file.

    Note: The file is named prompts.json but contains a Python dict literal
    of the form { "키": \"\"\" ... \"\"\", ... }. We therefore use
    ast.literal_eval for safe parsing instead of json.load.
    """
    api_dir = os.path.dirname(os.path.abspath(__file__))
    path = file_path or os.path.join(api_dir, "prompts.json")

    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        data = ast.literal_eval(content)
        if isinstance(data, dict):
            # Ensure all values are strings
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def parse_category_prompt_response(text: str) -> Tuple[Optional[int], str]:
    """
    Parse a single-category prompt response of the form:
      폭력성 점수: {0~3}점
      근거: {서술}

    Returns (score_or_none, reason_text).
    If a score cannot be found, returns (None, full_text).
    """
    if not isinstance(text, str):
        return None, ""

    score: Optional[int] = None
    # find first integer 0-4 after "점수" token (allow variations)
    m = re.search(r'점\s*수?\s*[:：]?\s*([0-4])', text)
    if m:
        try:
            score = int(m.group(1))
        except ValueError:
            score = None

    # extract reason after "근거:" if present, else fallback to whole text
    reason = text.strip()
    rm = re.search(r'근거\s*[:：]\s*(.+)$', text, re.DOTALL)
    if rm:
        reason = rm.group(1).strip()

    return score, reason


