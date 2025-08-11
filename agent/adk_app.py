import os
from google.adk.agents import LlmAgent

# Bridge GEMINI_API_KEY -> GOOGLE_API_KEY for google-genai used by ADK
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

DEFAULT_INSTRUCTION = (
    "あなたは日本国内旅行のプランナーです。次のJSON入力（ペルソナ/プロファイル/制約）を読み、"
    "3つの旅行プランを日本語で提案してください。出力は必ず次の形式のみで返してください。\n\n"
    "入力例:\n"
    "{\n  \"persona\":{\"title\":\"◯◯タイプ\",\"description\":\"...\",\"traitScores\":{}},\n"
    "  \"profile\":{\"display_name\":\"...\"},\n  \"constraints\":{\"season\":\"春\"}\n}\n\n"
    "出力(JSONのみ):\n"
    "{\n  \"plans\": [\n    {\"title\": \"...\", \"description\": \"...\"},\n"
    "    {\"title\": \"...\", \"description\": \"...\"},\n"
    "    {\"title\": \"...\", \"description\": \"...\"}\n  ]\n}\n\n"
    "制約:\n- 国内旅行に限定\n- 地域はなるべく分散（北/東/西など）\n- 日本語で簡潔に\n"
)

INSTRUCTION = os.getenv("AGENT_INSTRUCTION_OVERRIDE") or DEFAULT_INSTRUCTION

# Root agent exposed to ADK Web/UI
root_agent = LlmAgent(
    name="travel_planner",
    model=MODEL,
    description="Generate domestic travel plans in Japanese from persona/profile/constraints",
    instruction=INSTRUCTION,
)
