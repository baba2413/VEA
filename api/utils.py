import base64
import os
import shutil
import subprocess
import tempfile
from typing import List, Tuple, Optional

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


