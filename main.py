# 📋 main.py · [과제 백엔드] 나만의 멀티모달 API — 사진을 받아 정해 둔 칸(JSON)으로 정리 (Vercel 에 올릴 main.py · POST 한 번에 요청 1번)
# · ★ (직접 작성) 표시가 붙은 곳만 내 주제로 바꾸면 됨 — 화면(app.py)은 고칠 곳 없음
# · 키는 환경 변수 GEMINI_API_KEY · 접근 코드는 APP_ACCESS_CODE (코드 · 저장소에 적지 않음)
import base64
import binascii
import json
import os

from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

MODEL_NAME = "gemini-3.5-flash-lite"

# ★ (직접 작성) ① 서비스 이름 · 아이콘 · 한 줄 소개 — 화면이 GET / 로 받아 제목으로 씀
APP_TITLE = "벌크업 식단 기록 도우미"
APP_ICON = "🍱"
APP_DESCRIPTION = "식사 사진을 찍으면 음식 · 대략의 양 · 단백질 재료를 정리하고 한 줄 평을 해 줍니다 (참고용 — AI 가 틀릴 수 있음)"

# ★ (직접 작성) ② 사진을 보고 할 일 — 역할 · 할 일 · 모를 때
PROMPT = """너는 운동하면서 근육량을 늘리려는(벌크업) 대학생의 식단 기록을 도와주는 도우미야.
사진이 음식 · 식사 사진이면 아래 칸을 채워. 사진에서 알 수 없는 칸은 '확인 불가' 라고 적어.
양은 '밥 한 공기 정도' 처럼 눈으로 본 어림으로만 적고, 칼로리 · 영양 성분 숫자는 지어내지 마.
음식 사진이 아니면 모든 칸에 '음식 사진이 아님' 이라고 적어. 사진 속 사람에 대해서는 말하지 마."""

# ★ (직접 작성) ③ 결과로 받을 칸 이름 : 설명 (3~5개)
FIELDS = {
    "음식": "사진에 보이는 음식 이름들 (쉼표로 구분)",
    "대략의 양": "음식마다 눈으로 본 대략의 양 (예: 밥 한 공기 정도)",
    "단백질 재료": "단백질이 많은 재료 (없으면 '없음')",
    "한 줄 평": "벌크업 식단으로 어떤지 한 문장 평 (부족한 것이 있으면 무엇을 더하면 좋은지)",
}

SCHEMA = {"type": "object", "properties": {name: {"type": "string", "description": text} for name, text in FIELDS.items()},
          "required": list(FIELDS)}
app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION)


class PhotoRequest(BaseModel):
    image_b64: str = Field(min_length=1, max_length=4_000_000, description="사진(JPEG)을 base64 로 바꾼 글자")


class Result(BaseModel):
    result: dict[str, str]
    tokens: int | None = None


def check_access(access_code):
    expected = os.environ.get("APP_ACCESS_CODE")
    if expected and access_code != expected:
        raise HTTPException(status_code=401, detail="접근 코드가 틀렸습니다 — 헤더 X-Access-Code 를 확인하세요")


def get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="서버에 GEMINI_API_KEY 가 없습니다 — 환경 변수를 확인하세요")
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=120_000, retry_options=types.HttpRetryOptions(http_status_codes=[500, 503])),
    )


@app.get("/")
def home():
    """화면이 제목 · 아이콘 · 소개 · 칸 이름을 가져가는 주소 (요청 없음)"""
    return {"name": APP_TITLE, "icon": APP_ICON, "description": APP_DESCRIPTION, "fields": list(FIELDS)}


@app.post("/analyze", response_model=Result)
def analyze(request: PhotoRequest, x_access_code: str | None = Header(default=None)):
    check_access(x_access_code)
    try:
        base64.b64decode(request.image_b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="base64 글자가 아닙니다")
    client = get_client()
    try:
        reply = client.interactions.create(
            model=MODEL_NAME, store=False,
            input=[{"type": "text", "text": PROMPT}, {"type": "image", "data": request.image_b64, "mime_type": "image/jpeg"}],
            response_format={"type": "text", "mime_type": "application/json", "schema": SCHEMA},
        )
    except Exception as error:
        code = getattr(error, "status_code", None)
        raise HTTPException(status_code=429 if code == 429 else 502, detail=f"Gemini 요청 실패 (상태 번호 {code})")
    try:
        result = json.loads(reply.output_text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="답이 JSON 모양이 아닙니다 — 다시 보내 보세요")
    return Result(result={name: str(result.get(name, "")) for name in FIELDS}, tokens=reply.usage.total_tokens)

# ============================================================
# 아래는 13주차 과제 · 실습 화면이 쓰던 주소 — 같은 저장소(my-ai-api)를 다시 쓰므로 그대로 남겨 둠
# ============================================================
ROUTINE_PROMPT = """너는 '루틴봇'이야. 헬스를 막 시작한 사람에게 운동 루틴과 자세를 알려 주는 도우미야.
규칙 1. {tone} 말투로 4문장 이내로 답한다.
규칙 2. 운동 이름 · 세트 수와 반복 횟수 · 자세에서 주의할 점을 알려 준다.
규칙 3. 운동과 관련 없는 질문에는 '저는 운동 도우미라서 그 질문에는 답하기 어려워요.' 라고 답한다. 통증 · 부상 · 약에 대한 진단이나 처방은 하지 않고 병원에 가 보라고 안내한다.
규칙 4. 헬스장 가격 · 영업시간 · 보충제 성분처럼 모르는 정보는 지어내지 말고 직접 확인하라고 안내한다.
규칙 5. 이름 · 나이 · 몸무게 · 전화번호 같은 개인정보를 묻지 않는다."""
EXAMPLE_QUESTIONS = ["헬스 처음인데 주 3일 루틴 짜 줘.", "스쿼트할 때 무릎이 안쪽으로 모이는데 어떻게 고쳐?", "집에서 덤벨만으로 할 수 있는 등 운동?"]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=300, description="질문")
    tone: str = Field(default="친근한 존댓말", max_length=20, description="답의 말투")


class AskReply(BaseModel):
    question: str
    answer: str
    tokens: int | None = None


class Question(BaseModel):
    word: str = Field(min_length=1, max_length=30, description="궁금한 용어")
    style: str = Field(default="초등학생도 알아듣게 쉽게", description="설명 말투")


class Answer(BaseModel):
    word: str
    answer: str
    tokens: int | None = None


def ask_text(system_instruction, text):
    """글만 보내는 요청 (13주차와 같음)"""
    client = get_client()
    try:
        return client.interactions.create(model=MODEL_NAME, store=False, system_instruction=system_instruction, input=text)
    except Exception as error:
        code = getattr(error, "status_code", None)
        raise HTTPException(status_code=429 if code == 429 else 502, detail=f"Gemini 요청 실패 (상태 번호 {code})")


@app.get("/examples")
def examples():
    return {"examples": EXAMPLE_QUESTIONS}


@app.post("/ask", response_model=AskReply)
def ask(request: AskRequest, x_access_code: str | None = Header(default=None)):
    check_access(x_access_code)
    reply = ask_text(ROUTINE_PROMPT.format(tone=request.tone), request.question)
    return AskReply(question=request.question, answer=reply.output_text, tokens=reply.usage.total_tokens)


@app.post("/explain", response_model=Answer)
def explain(question: Question, x_access_code: str | None = Header(default=None)):
    check_access(x_access_code)
    reply = ask_text(f"너는 AI 용어 설명 도우미야. {question.style} 3문장 이내로 설명한다.", question.word)
    return Answer(word=question.word, answer=reply.output_text, tokens=reply.usage.total_tokens)


# ============================================================
# 아래는 14주차 실습 G(사진 · 음성 도우미)의 주소 — POST /describe · POST /listen
# ============================================================
MAX_B64 = 4_000_000                 # base64 글자 수 상한 — Vercel 요청 본문 4.5MB 보다 조금 작게
VOICE_PROMPTS = {
    "받아쓰기": "이 음성을 한국어로 그대로 받아써 줘. 잘 안 들리는 부분은 (?) 로 표시해 줘.",
    "한 줄 요약": "이 음성의 내용을 한 문장으로 요약해 줘.",
    "영어로 번역": "이 음성의 내용을 자연스러운 영어로 번역해 줘.",
}


class DescribeRequest(BaseModel):
    image_b64: str = Field(min_length=1, description="사진(JPEG · PNG)을 base64 로 바꾼 글자")
    mime_type: Literal["image/jpeg", "image/png"] = "image/jpeg"
    question: str = Field(default="이 사진에 무엇이 있는지 3문장 이내로 설명해 줘.", max_length=300)


class VoiceRequest(BaseModel):
    audio_b64: str = Field(min_length=1, description="녹음(WAV)을 base64 로 바꾼 글자")
    task: Literal["받아쓰기", "한 줄 요약", "영어로 번역"] = "받아쓰기"


class MediaAnswer(BaseModel):
    answer: str
    tokens: int | None = None


def check_b64(text):
    """base64 글자가 맞는지 · 너무 크지 않은지 먼저 검사 — 틀리면 Gemini 까지 가지 않음"""
    if len(text) > MAX_B64:
        raise HTTPException(status_code=413, detail="파일이 너무 큽니다 — 사진은 줄이고, 녹음은 짧게 보내세요")
    try:
        base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="base64 글자가 아닙니다 — 화면에서 b64encode 했는지 확인하세요")


def ask_media(text, part):
    """글 부분 + 사진(음성) 부분을 Gemini 에 보내고 답을 돌려줌"""
    client = get_client()
    try:
        reply = client.interactions.create(model=MODEL_NAME, store=False, input=[{"type": "text", "text": text}, part])
    except Exception as error:
        code = getattr(error, "status_code", None)
        raise HTTPException(status_code=429 if code == 429 else 502, detail=f"Gemini 요청 실패 (상태 번호 {code})")
    return MediaAnswer(answer=reply.output_text, tokens=reply.usage.total_tokens)


@app.post("/describe", response_model=MediaAnswer)
def describe(request: DescribeRequest, x_access_code: str | None = Header(default=None)):
    check_access(x_access_code)                     # ① 접근 코드
    check_b64(request.image_b64)                    # ② 크기 · base64 검사
    return ask_media(request.question, {"type": "image", "data": request.image_b64, "mime_type": request.mime_type})


@app.post("/listen", response_model=MediaAnswer)
def listen(request: VoiceRequest, x_access_code: str | None = Header(default=None)):
    check_access(x_access_code)
    check_b64(request.audio_b64)
    return ask_media(VOICE_PROMPTS[request.task], {"type": "audio", "data": request.audio_b64, "mime_type": "audio/wav"})
