import time
import json
import os
import re
import copy
from pathlib import Path
from typing import Optional
from datetime import datetime
from google import genai
from concurrent.futures import ThreadPoolExecutor, as_completed


def analyze_video_with_gemini(
    video_path: str, 
    prompt: Optional[str] = None, 
    model: str = "gemini-2.5-flash"
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


def analyze_with_gemini(prompt:str) -> str:
    client = genai.Client()
    if not prompt:
        prompt="프롬프트가 지정되지 않았으므로 이를 사용자에게 알리시오."

    resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
            )
    
    if hasattr(resp, "text") and resp.text:
        return resp.text
    # Fallback: combine parts if text missing
    try:
        return "\n".join(p.text for p in resp.candidates[0].content.parts if getattr(p, "text", None))
    except Exception:
        return str(resp)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JSON_PATHS = {
    "video_text":      os.path.join(BASE_DIR, "..", "tools", "video_text.json"),
    "prompts":         os.path.join(BASE_DIR, "..", "api", "prompts.json"),
    "considerations":  os.path.join(BASE_DIR, "..", "api", "considerations.json"),
    "analysis_results":os.path.join(BASE_DIR, "..", "api", "analysis_results.json"),
    "feedbacks":       os.path.join(BASE_DIR, "..", "api", "feedbacks.json"),
    "is_prompt_changed": os.path.join(BASE_DIR, "..", "api", "is_prompt_changed.json"),
}

DATA: dict[str, dict] = {} # cache

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def refresh(name: str):
    path = JSON_PATHS[name]
    DATA[name] = load_json(path)

def refresh_all():
    for name in JSON_PATHS:
        refresh(name)

refresh_all()


def make_prompt(file_name:str, criteria:str)->str:
    video_text = DATA["video_text"]
    prompts = DATA["prompts"]
    considerations = DATA["considerations"]

    prompt = f"""
        {video_text[file_name]}\n\n
        {prompts[criteria]}\n
        아래의 고려사항을 준수하여 심의한다.\n
        고려사항: {considerations[criteria]}\n\n
        반드시 출력 양식의 형태 그대로 출력한다.\n
        출력 양식은 다은과 같다.\n
        {criteria} : 0 or 1, 반드시 0 혹은 1의 값을 출력한다.\n
        근거: 감지된 민감 요소 및 근거 서술. 단, 텍스트가 아닌 영상 원본을 본 것처럼 서술한다. 영상 요약은 하지 않으며, 2문장 내외로 서술한다.
    """

    return prompt

def feedback_with_llm(file_name:str, criteria:str, feedback:str):
    video_text       = DATA["video_text"]
    analysis_results = DATA["analysis_results"]
    feedbacks        = DATA["feedbacks"]
    is_prompt_changed = DATA["is_prompt_changed"]

    detail = analysis_results[file_name]["details"][criteria]
    ox = analysis_results[file_name]["ox"][criteria]
    msg = f"{criteria} 기준 위반함. " if ox==1 else f"{criteria} 기준 위반하지 않음. "
    msg += detail

    prompt = f"""
        영상 심의 시스템의 유저가 영상을 보고 심의 내용에 대해 피드백을 작성하였다.\n
        당신은 피드백의 내용을 영상의 맥락을 고려하여 재작성한다.\n\n
        영상의 내용은 다음과 같다:\n
        {video_text[file_name]}\n\n
        기존 심의 내용은 다음과 같다:\n
        {msg}\n\n
        이에 대한 유저의 피드백은 다음과 같다:\n
        {feedback}\n\n
        피드백의 의미를 유지하면서 영상의 맥락이 담길 수 있게끔 문장을 작성한다. 100자를 넘기지 않는다.
    """
    result = analyze_with_gemini(prompt=prompt)
    feedbacks[criteria].append(result)
    with open(JSON_PATHS["feedbacks"], "w", encoding="utf-8") as f:
        json.dump(feedbacks, f, ensure_ascii=False, indent=2)

    is_prompt_changed[criteria] = 1
    with open(JSON_PATHS["is_prompt_changed"], "w", encoding="utf-8") as f:
        json.dump(is_prompt_changed, f, indent=2, ensure_ascii=False)


def feedback_with_video(video_path: str, file_name: str, criteria: str, feedback: str):
    """
    Video-based feedback - uses actual video file instead of text description

    Args:
        video_path: Path to the video file
        file_name: Name of the video file (for analysis_results lookup)
        criteria: The criteria being evaluated
        feedback: User's feedback text
    """
    analysis_results = DATA["analysis_results"]
    feedbacks        = DATA["feedbacks"]
    is_prompt_changed = DATA["is_prompt_changed"]

    detail = analysis_results[file_name]["details"][criteria]
    ox = analysis_results[file_name]["ox"][criteria]
    msg = f"{criteria} 기준 위반함. " if ox==1 else f"{criteria} 기준 위반하지 않음. "
    msg += detail

    prompt = f"""
        영상 심의 시스템의 유저가 영상을 보고 심의 내용에 대해 피드백을 작성하였다.\n
        당신은 피드백의 내용을 영상의 맥락을 고려하여 재작성한다.\n\n
        영상이 제공됩니다. 영상을 직접 확인하여 맥락을 파악하세요.\n\n
        기존 심의 내용은 다음과 같다:\n
        {msg}\n\n
        이에 대한 유저의 피드백은 다음과 같다:\n
        {feedback}\n\n
        피드백의 의미를 유지하면서 영상의 맥락이 담길 수 있게끔 문장을 작성한다. 100자를 넘기지 않는다.
    """

    # Upload video to Gemini
    client = genai.Client()
    file = client.files.upload(file=video_path)

    # Wait for processing to complete
    while file.state.name == "PROCESSING":
        time.sleep(0.5)
        file = client.files.get(name=file.name)

    if file.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini file upload failed: state={file.state.name}")

    # Call Gemini API with video
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[file, prompt],
    )

    if hasattr(resp, "text") and resp.text:
        result = resp.text
    else:
        try:
            result = "\n".join(p.text for p in resp.candidates[0].content.parts if getattr(p, "text", None))
        except Exception:
            result = str(resp)

    feedbacks[criteria].append(result)
    with open(JSON_PATHS["feedbacks"], "w", encoding="utf-8") as f:
        json.dump(feedbacks, f, ensure_ascii=False, indent=2)

    is_prompt_changed[criteria] = 1
    with open(JSON_PATHS["is_prompt_changed"], "w", encoding="utf-8") as f:
        json.dump(is_prompt_changed, f, indent=2, ensure_ascii=False)


def feedback_to_consideration(criteria:str):
    """
    Summarize accumulated feedbacks for a given criteria into considerations.

    Args:
        criteria: The criteria name (e.g., "violence", "sexuality", etc.)
    """
    feedbacks = DATA["feedbacks"]
    considerations = DATA["considerations"]

    # Get the list of feedbacks for this criteria
    feedback_list = feedbacks.get(criteria, [])

    # If no feedbacks, keep existing consideration
    if not feedback_list:
        return

    # Create prompt to summarize all feedbacks into a concise consideration
    feedback_text = "\n".join([f"- {fb}" for fb in feedback_list])

    prompt = f"""
        영상 심의 시스템에서 '{criteria}' 기준에 대해 누적된 유저 피드백들이 있다.
        이 피드백들을 종합하여 앞으로 심의 시 참고할 간결한 고려사항을 작성한다.

        누적된 피드백 목록:
        {feedback_text}

        위 피드백들의 핵심 내용을 반영하여, '{criteria}' 기준 심의 시 적용할 고려사항을 100자 이내로 작성한다.
        심의자가 참고할 명확한 지침 형태로 작성한다.
    """

    # Get summarized consideration from Gemini
    result = analyze_with_gemini(prompt=prompt)

    # Update considerations
    considerations[criteria] = result.strip()

    # Save to file
    with open(JSON_PATHS["considerations"], "w", encoding="utf-8") as f:
        json.dump(considerations, f, ensure_ascii=False, indent=2)

    # Refresh cache
    refresh("considerations")

def re_analyze():
    analysis_results = DATA["analysis_results"]
    is_prompt_changed = DATA["is_prompt_changed"]
    criteria = []

    for key,value in is_prompt_changed.items():
        if value == 1:
            criteria.append(key)
            feedback_to_consideration(key)

    # Build all (file_name, criteria) tasks to process
    tasks = []
    if criteria:
        for file_name in analysis_results:
            for c in criteria:
                tasks.append((file_name, c))

    def analyze_one(file_name: str, c: str):
        msg = make_prompt(file_name=file_name, criteria=c)
        new_result = analyze_with_gemini(msg)
        m1 = re.search(rf"{c}\s*:\s*(0|1)", new_result)
        new_ox = int(m1.group(1)) if m1 else -1
        m2 = re.search(r"근거\s*:\s*(.*)", new_result, re.DOTALL)
        new_detail = m2.group(1).strip() if m2 else "error"
        return file_name, c, new_ox, new_detail

    if tasks:
        max_workers = 1  # Temporarily set to 1 for testing (avoid rate limits)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(analyze_one, fn, c): (fn, c) for fn, c in tasks}
            for future in as_completed(futures):
                file_name, c, new_ox, new_detail = future.result()
                analysis_results[file_name]["ox"][c] = new_ox
                analysis_results[file_name]["details"][c] = new_detail
                time.sleep(6)  # Wait 6 seconds between requests (free tier: 10 req/min)
            
    output_path = Path(BASE_DIR) / "analysis_results_new.json"
    output_path.write_text(
        json.dumps(analysis_results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def is_result_changed():
    with open(Path(BASE_DIR) / "analysis_results.json", encoding="utf-8") as f:
        analysis_results_old = json.load(f)
    is_prompt_changed = DATA["is_prompt_changed"]
    with open(Path(BASE_DIR) / "analysis_results_new.json", encoding="utf-8") as f:
        analysis_results_new = json.load(f)

    criteria = []
    for key,value in is_prompt_changed.items():
        if value == 1:
            criteria.append(key)

    is_ox_changed = {}
    
    for key,value in analysis_results_old.items():
        is_changed = []
        for c in criteria:
            ox_old = value["ox"][c]
            ox_new = analysis_results_new[key]["ox"][c]
            if ox_old != ox_new:
                is_changed.append(c)
        is_ox_changed[key] = is_changed

    (Path(BASE_DIR) / "is_ox_changed.json").write_text(
        json.dumps(is_ox_changed, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(BASE_DIR, "log")
    os.makedirs(log_dir, exist_ok=True)
    # Save both old and new snapshots for traceability
    log_old = os.path.join(log_dir, f"analysis_results_old_{timestamp}.json")
    with open(log_old, "w", encoding="utf-8") as f:
        json.dump(analysis_results_old, f, ensure_ascii=False, indent=2)
    log_new = os.path.join(log_dir, f"analysis_results_new_{timestamp}.json")
    with open(log_new, "w", encoding="utf-8") as f:
        json.dump(analysis_results_new, f, ensure_ascii=False, indent=2)
    (Path(BASE_DIR) / "analysis_results.json").write_text(
        json.dumps(analysis_results_new, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    # Keep in-memory cache consistent with the newly persisted baseline
    refresh("analysis_results")

    for key in is_prompt_changed:
        is_prompt_changed[key] = 0 
    with open(os.path.join(BASE_DIR, "is_prompt_changed.json"), "w", encoding="utf-8") as f:
        json.dump(is_prompt_changed, f, indent=2, ensure_ascii=False)

# # Test
# def main():
#     # feedback_with_llm("sample (1).mp4","violence","담배를 피우는건 폭력성 관련 내용이 아님.")
#     re_analyze()
#     is_result_changed()
# from pathlib import Path
# import sys
# sys.path.insert(0, str(Path(__file__).parent.parent))
# from api.utils import load_environment, ensure_env
# if __name__ == "__main__":
#     load_environment()
#     ensure_env("GOOGLE_API_KEY")
#     main()