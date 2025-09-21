import os
import logging
from google.adk.agents import LlmAgent
from .travel_planner.agent import travel_planner_agent  # type: ignore
from .travel_advisor.agent import travel_advisor_agent  # type: ignore
from .travel_modifier.agent import travel_modifier_agent  # type: ignore
from .general_chat.agent import general_chat_agent  # type: ignore

# Minimal logging setup
_LEVEL = (os.getenv("LOG_LEVEL") or "INFO").upper()
logging.basicConfig(level=getattr(logging, _LEVEL, logging.INFO), format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
log = logging.getLogger("agent.root_coordinator")

# Ensure google-genai (used by ADK) can authenticate with API key in local dev
if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
	os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY") or ""
	log.info("GOOGLE_API_KEY not set; using GEMINI_API_KEY as fallback for local dev")

# MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
MODEL = "gemini-2.5-flash-lite"
log.info(f"Root Coordinator Agent model: {MODEL}")

ROOT_COORDINATOR_INSTRUCTION = (
	"あなたは旅行アシスタントのコーディネーターです。ユーザーのリクエストを分析し、適切なサブエージェントに振り分けます。\n\n"
	"利用可能なサブエージェント：\n"
	"1) travel_planner: 新しい旅行プランの作成。persona/profile情報から3つの旅行プランを生成\n"
	"2) travel_modifier: 既存プランの修正/最適化/制約変更に基づく更新案の作成\n"
	"3) travel_advisor: 旅行当日のサポート。既存のプランと現在の状況に基づいてアドバイスを提供\n"
	"4) general_chat: 一般的な旅行相談と位置情報に基づく案内。周辺スポット検索や交通案内\n\n"
	"判断基準：\n"
	"- 新しい旅行プランの作成依頼 → travel_planner\n"
	"- 既存プランの修正/日程調整/制約変更の反映 → travel_modifier\n"
	"- 当日のトラブル対応やリアルタイム案内 → travel_advisor\n"
	"- 位置情報を含む一般的な質問や周辺情報の問い合わせ → general_chat\n"
	"- 旅行プランに関係ない一般的な旅行相談 → general_chat\n"
	"- 判断が困難な場合は general_chat を選択\n\n"
	"あなたは選択したサブエージェントの応答をそのまま返すことが役割です。レスポンスの形式を変更してはいけません。"
)

root_agent = LlmAgent(
	name="root_coordinator",
	model=MODEL,
	description="Coordinate requests to appropriate sub-agents (travel_planner, travel_modifier, travel_advisor, general_chat)",
	instruction=ROOT_COORDINATOR_INSTRUCTION,
	sub_agents=[travel_planner_agent, travel_modifier_agent, travel_advisor_agent, general_chat_agent],
	tools=[],  # Root agent doesn't need direct tools, sub-agents handle them
)
log.info(f"Root Coordinator Agent initialized with {len(root_agent.sub_agents)} sub-agent(s)")