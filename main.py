# 📋 main.py · 과제 — 나만의 AI API
# ============================================================
# 13주차 오늘의 과제 · 나만의 AI API (main.py)
# ------------------------------------------------------------
# · ★ (직접 작성) 표시가 붙은 곳만 내 주제로 바꾸면 됨
# · 키는 서버 환경 변수 GEMINI_API_KEY 로만 읽음 (Vercel → Settings → Environment Variables)
# · 접근 코드는 환경 변수 APP_ACCESS_CODE — 부르는 쪽은 헤더 X-Access-Code 에 같은 값을 넣음
#   ★ 이 파일 · GitHub 저장소에 키와 접근 코드를 절대 적지 않음
# · POST /ask 한 번에 Gemini 요청 1번 (무료 한도 분당 15회)
# ============================================================
import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

MODEL_NAME = "gemini-3.5-flash-lite"

# ★ (직접 작성) ① API 이름 · 한 줄 소개
APP_TITLE = "헬스 루틴 API"
APP_DESCRIPTION = "헬스를 막 시작한 사람에게 운동 루틴과 자세를 알려 주는 AI API"

# ★ (직접 작성) ② 시스템 프롬프트 — 11주차 설계표 여섯 칸 · {tone} 자리에는 요청의 말투가 들어감 (지우지 말 것)
SYSTEM_PROMPT = """너는 '루틴봇'이야. 헬스를 막 시작한 사람에게 운동 루틴과 자세를 알려 주는 도우미야.
규칙 1. {tone} 말투로 4문장 이내로 답한다.
규칙 2. 운동 이름 · 세트 수와 반복 횟수 · 자세에서 주의할 점을 알려 준다.
규칙 3. 운동과 관련 없는 질문에는 '저는 운동 도우미라서 그 질문에는 답하기 어려워요.' 라고 답한다. 통증 · 부상 · 약에 대한 진단이나 처방은 하지 않고 병원에 가 보라고 안내한다.
규칙 4. 헬스장 가격 · 영업시간 · 보충제 성분처럼 모르는 정보는 지어내지 말고 직접 확인하라고 안내한다.
규칙 5. 이름 · 나이 · 몸무게 · 전화번호 같은 개인정보를 묻지 않는다."""

# ★ (직접 작성) ③ 예시 질문 3개 (GET /examples 가 돌려줌)
EXAMPLE_QUESTIONS = ["헬스 처음인데 주 3일 루틴 짜 줘.", "스쿼트할 때 무릎이 안쪽으로 모이는데 어떻게 고쳐?", "집에서 덤벨만으로 할 수 있는 등 운동?"]

app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=300, description="질문")
    tone: str = Field(default="친근한 존댓말", max_length=20, description="답의 말투")


class AskReply(BaseModel):
    question: str
    answer: str
    tokens: int | None = None


def check_access(access_code):
    """APP_ACCESS_CODE 가 정해져 있으면, 헤더의 접근 코드가 같아야만 통과"""
    expected = os.environ.get("APP_ACCESS_CODE")
    if expected and access_code != expected:
        raise HTTPException(status_code=401, detail="접근 코드가 틀렸습니다 — 헤더 X-Access-Code 를 확인하세요")


def get_client():
    """키는 서버의 환경 변수 GEMINI_API_KEY 에서 읽음"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="서버에 GEMINI_API_KEY 가 없습니다 — 환경 변수를 확인하세요")
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=60_000, retry_options=types.HttpRetryOptions(http_status_codes=[500, 503])),
    )


@app.get("/")
def home():
    return {"name": APP_TITLE, "description": APP_DESCRIPTION, "how_to_use": "POST /ask 에 {\"question\": \"…\"} 를 보내세요. 자세한 사용법은 /docs"}


@app.get("/examples")
def examples():
    return {"examples": EXAMPLE_QUESTIONS}


@app.post("/ask", response_model=AskReply)
def ask(request: AskRequest, x_access_code: str | None = Header(default=None)):
    check_access(x_access_code)
    client = get_client()
    try:
        reply = client.interactions.create(
            model=MODEL_NAME, store=False,
            system_instruction=SYSTEM_PROMPT.format(tone=request.tone),
            input=request.question,
        )
    except Exception as error:
        code = getattr(error, "status_code", None)
        if code == 429:
            raise HTTPException(status_code=429, detail="Gemini 무료 한도를 넘었습니다 — 1분 뒤 다시 요청하세요")
        raise HTTPException(status_code=502, detail=f"Gemini 요청 실패 (상태 번호 {code})")
    return AskReply(question=request.question, answer=reply.output_text, tokens=reply.usage.total_tokens)


# ---- 수업 실습 7-1 화면(AI 용어 설명기)이 부르는 주소 ----
class Question(BaseModel):
    word: str = Field(min_length=1, max_length=30, description="궁금한 용어")
    style: str = Field(default="초등학생도 알아듣게 쉽게", description="설명 말투")


class Answer(BaseModel):
    word: str
    answer: str
    tokens: int | None = None


@app.post("/explain", response_model=Answer)
def explain(question: Question, x_access_code: str | None = Header(default=None)):
    check_access(x_access_code)
    client = get_client()
    try:
        reply = client.interactions.create(
            model=MODEL_NAME, store=False,
            system_instruction=f"너는 AI 용어 설명 도우미야. {question.style} 3문장 이내로 설명한다.",
            input=question.word,
        )
    except Exception as error:
        code = getattr(error, "status_code", None)
        if code == 429:
            raise HTTPException(status_code=429, detail="Gemini 무료 한도를 넘었습니다 — 1분 뒤 다시 요청하세요")
        raise HTTPException(status_code=502, detail=f"Gemini 요청 실패 (상태 번호 {code})")
    return Answer(word=question.word, answer=reply.output_text, tokens=reply.usage.total_tokens)
