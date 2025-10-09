from google import genai
from api.utils import load_environment, ensure_env, extract_audio_from_video, has_ffmpeg
load_environment()
ensure_env("GOOGLE_API_KEY")
client = genai.Client()

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Explain how AI works in a few words",
)

print(response.text)