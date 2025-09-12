import os
import logging
from google.adk.agents import LlmAgent
from travel_planner.agent import travel_planner_agent  # type: ignore
from travel_advisor.agent import travel_advisor_agent  # type: ignore

# Minimal logging setup
_LEVEL = (os.getenv("LOG_LEVEL") or "INFO").upper()
logging.basicConfig(level=getattr(logging, _LEVEL, logging.INFO), format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
log = logging.getLogger("agent.root_coordinator")

# MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
MODEL = "gemini-2.5-flash-lite"
log.info(f"Root Coordinator Agent model: {MODEL}")

ROOT_COORDINATOR_INSTRUCTION = (
	"あなたは旅行アシスタントのコーディネーターです。ユーザーのリクエストを分析し、適切なサブエージェントに振り分けます。\n\n"
	"利用可能なサブエージェント：\n"
	"1) travel_planner: 新しい旅行プランの作成。persona/profile情報から3つの旅行プランを生成\n"
	"2) travel_advisor: 旅行当日のサポート。既存のプランと現在の状況に基づいてアドバイスを提供\n\n"
	"判断基準：\n"
	"- 新しい旅行プランの作成依頼 → travel_planner\n"
	"- 既存プランの修正、当日のトラブル対応、リアルタイム情報 → travel_advisor\n"
	"- 判断が困難な場合は travel_planner を選択\n\n"
	"あなたは選択したサブエージェントの応答をそのまま返すことが役割です。レスポンスの形式を変更してはいけません。"
)



root_agent = LlmAgent(
	name="root_coordinator",
	model=MODEL,
	description="Coordinate requests to appropriate sub-agents (travel_planner or travel_advisor)",
	instruction=ROOT_COORDINATOR_INSTRUCTION,
	sub_agents=[travel_planner_agent, travel_advisor_agent],
	tools=[],  # Root agent doesn't need direct tools, sub-agents handle them
)
log.info(f"Root Coordinator Agent initialized with {len(root_agent.sub_agents)} sub-agent(s)")