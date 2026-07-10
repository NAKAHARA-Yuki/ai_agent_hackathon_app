import os
import logging
from google.adk.agents import LlmAgent  # type: ignore
# Tools
from google.adk.tools import google_search  # type: ignore

log = logging.getLogger("agent.general_chat")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
log.info(f"General Chat Agent model: {MODEL}")

# Fallback for ADK/google-genai API key in local dev
if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY") or ""
    log.info("GOOGLE_API_KEY not set; using GEMINI_API_KEY as fallback for local dev (general_chat)")

GENERAL_CHAT_INSTRUCTION = (
    "あなたは一般的な旅行相談と位置情報に基づく案内を行う旅行アシスタントです。\n\n"
    "役割:\n"
    "- 現在位置やユーザー質問に基づき、観光スポット/飲食店/施設/移動案内/注意喚起などを日本語で案内する。\n"
    "- 不明点は無理に断定せず、調べ方の提案も行う。\n\n"
    "位置情報が提供された場合:\n"
    "- 必要に応じて Google 検索ツールを使用し、必要情報を取得・要約して統合する。\n"
    "- 具体的な場所名、住所、営業時間、口コミ/評価、所要時間などの実用情報を含める。\n"
    "- 徒歩/電車/バス/自転車など現実的な移動手段と概算時間を併記。\n\n"
    "検索結果の取り扱い：必要最小限の引用に留め、根拠となる情報は統合して平易に要約する。生の検索レスポンスは貼り付けない。\n\n"
    "(EN Warning) Output exactly ONE raw JSON object only. No markdown headings/tables/fences. Any extra text may cause rejection."
)

# Initialize tools - use Google Search (ADK built-in)
general_chat_agent = LlmAgent(
    name="general_chat",
    model=MODEL,
    description="General travel chat agent using Google Search for up-to-date info",
    instruction=GENERAL_CHAT_INSTRUCTION,
    tools=[google_search],
)

log.info(f"General Chat Agent initialized with {len(general_chat_agent.tools)} tool(s)")