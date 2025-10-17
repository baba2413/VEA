import time
from typing import Optional

from google import genai


def analyze_video_with_gemini(
    video_path: str, 
    prompt: Optional[str] = None, 
    model: str = "gemini-2.0-flash-exp"
    ) -> str:

    client = genai.Client()
    if not prompt:
        prompt = (
            """
                당신의 임무는 영상 등급 심의 전문가로서 주어진 30초 가량의 영상의 내용을 아래 7가지 기준에 따라 분석하고 평가하는 것아다.
                영상의 장면, 대사, 음향, 분위기, 표현 방식 등을 종합적으로 고려하라.

                [평가 기준]

                1. 주제 및 내용: 사회 통념상 부적절하거나 불법, 차별, 비윤리적 행위를 미화·조장하는 주제가 포함되어 있는가?
                2. 선정성: 노출, 성행위 묘사, 성적 자극을 유발하는 대사나 장면이 있는가?
                3. 폭력성: 폭력 행위, 살상, 신체 훼손, 학대 등의 장면이 얼마나 자극적으로 표현되었는가?
                4. 공포: 과도한 공포감, 혐오감, 불쾌감을 주는 장면이나 연출이 있는가?
                5. 약물: 알코올, 마약, 흡연 등 약물 사용이 미화되거나 묘사되는가?
                6. 언어: 비속어, 욕설, 차별적·혐오적 발언, 위협적 언어 표현이 있는가?
                7. 모방 위험성: 위험하거나 비행을 조장할 수 있는 행위(폭력, 자해, 범죄 등)가 실제로 따라할 위험이 있는가?

                각 기준에서 0에서 4까지의 점수를 매긴다. 0은 전체 이용가, 4는 청소년 이용불가 수준이다.

                [출력 형식]
                내용 요약: [영상 내용 요약]

                1. 주제 및 내용: [점수(0~4)], [근거 또는 장면 설명]
                2. 선정성: ...
                3. 폭력성: ...
                4. 공포: ...
                5. 약물: ...
                6. 언어: ...
                7. 모방 위험성: ...

                - 종합의견: [영상의 주요 문제 요약]

                [주의]
                분석 시 객관적 근거에 기반하여, 감정적 표현보다는 명확한 사실과 장면 묘사를 중심으로 작성한다.
                반드시 출력 형식 외의 내용은 포함하지 않는다.
            """
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


