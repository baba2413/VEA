## VEA

### API Test

### 1) 셋업

1. venv/conda 가상환경 python 3.10
2. pip install -r requirements.txt
3. .env 만들고 키 채워넣기
```bash
copy .env.example .env  # Windows
```
4. ffmpeg 설치 방법
      Windows: winget install ffmpeg
      Mac: brew install ffmpeg
      Linux: sudo apt install ffmpeg (Ubuntu/Debian)


### 2) 사용법

기본 사용방법은 `cli.py`.

```bash
python cli.py --help
```

Common flows:

- Gemini:

```bash
python cli.py --video sample_videos\sample(1).mp4 --gemini
```


- Run all:

```bash
python cli.py --video path\to\sample.mp4 --all
```

video_clipper.py 사용법

```bash
python video_clipper.py input_video.mp4 -o ./clips
```

입력된 비디오를 30초단위로 잘라서 지정 폴더에 저장.

### video_analyzer.py

tools 폴더에 있음

같은 폴더의 input.json을 읽고 다운로드->Gemini API 이후 결과를 results.json에 씀.

영상은 yt_shorts 폴더에 다운로드됨.

input.json과 results.json 형식은 video_analyzer.py 에 주석으로 있음.


### 3) Notes

- Gemini video upload accepts common formats like MP4/MOV; larger files may take time to process.
- OpenAI vision is exercised by sampling a handful of frames from the video and sending them as images in a multimodal prompt; it is not true full-video upload.
- For audio transcription, the tool prefers `gpt-4o-mini-transcribe` and falls back to `whisper-1` if desired.

### 4) Environment Variables

Create `.env` with:

```
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
```

### 5) Safety & Costs

- Calls to LLM APIs may incur costs. Use short clips and enable lower-cost models in flags when exploring.
- Do not upload sensitive content.

### 6) 커밋 규칙
브랜치 이름에 규칙성
- impl: 구현함
- file: 파일 올림 
- ref: 리팩토링함
- fix: 버그 고침
- etc: 기타

예: `impl:api-test` 브랜치 생성 후 메인에 merge

### 7) 기타

샘플 영상 출처 (BigBuckBunny): https://gist.github.com/jsturgis/3b19447b304616f18657

conda activate vea_api

python cli.py --video sample_videos\sample(1).mp4 --gemini
