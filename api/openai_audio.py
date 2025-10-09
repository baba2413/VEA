from typing import Optional

from openai import OpenAI


def transcribe_audio_with_openai(audio_path: str, model: str = "gpt-4o-mini-transcribe") -> str:
    client = OpenAI()
    # Prefer new transcription-capable model name; fallback to whisper if needed by user.
    try:
        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model=model,
                file=f,
            )
        # SDK may return .text or nested data depending on version
        text = getattr(transcript, "text", None)
        if text:
            return text
        return str(transcript)
    except Exception:
        # Fallback to whisper-1 if the above fails (older accounts/regions)
        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
            )
        return getattr(transcript, "text", str(transcript))


