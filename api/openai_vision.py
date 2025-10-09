from typing import List, Optional

from openai import OpenAI

from .utils import sample_video_frames, encode_frame_to_data_url


def analyze_video_with_openai(
    video_path: str,
    num_frames: int = 8,
    prompt: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> str:

    if not prompt:
        prompt = (
            "Given the following sampled frames from a ~30 second video, describe objects, scenes, and any policy-relevant or unsafe content."
        )

    frames = sample_video_frames(video_path, num_frames=num_frames)
    images = [encode_frame_to_data_url(f) for f in frames]

    client = OpenAI()
    content: List[dict] = [{"type": "text", "text": prompt}]
    for data_url in images:
        content.append({"type": "image_url", "image_url": {"url": data_url}})

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""


