import time
from typing import Optional

from google import genai


def analyze_video_with_gemini(
    video_path: str, 
    prompt: Optional[str] = None, 
    model: str = "gemini-2.5-flash"
    ) -> str:

    client = genai.Client()
    if not prompt:
        prompt = (
            "You will see a short video. Describe notable objects, scenes, and any risky or policy-relevant content."
        )

    file = client.files.upload(file=video_path)

    # Wait for processing to complete
    while file.state.name == "PROCESSING":
        time.sleep(1.0)
        file = client.files.get(name=file.name)
    if file.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini file upload failed: state={file.state.name}")

    resp = client.models.generate_content(
                model=model,
                contents=[file, prompt],
                )
    if hasattr(resp, "text") and resp.text:
        return resp.text
    # Fallback: combine parts if text missing
    try:
        return "\n".join(p.text for p in resp.candidates[0].content.parts if getattr(p, "text", None))
    except Exception:
        return str(resp)


