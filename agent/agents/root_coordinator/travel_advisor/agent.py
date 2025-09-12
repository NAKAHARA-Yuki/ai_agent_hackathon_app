import os
import sys
import logging
from google.adk.agents import LlmAgent
# Tools
from google.adk.tools import google_search   # type: ignore

# Ensure agent/ is importable so we can access tools/maps_mcp
_here = os.path.dirname(__file__)
_agent_base = os.path.abspath(os.path.join(_here, '..', '..'))  # agent/agents -> agent
if _agent_base not in sys.path:
	sys.path.insert(0, _agent_base)

log = logging.getLogger("agent.travel_advisor")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
log.info(f"Travel Advisor Agent model: {MODEL}")

TRAVEL_ADVISOR_INSTRUCTION = (
	"あなたは旅行当日サポート専門のAIアドバイザーです。必ず JSON オブジェクト 1 個【のみ】を出力します。JSON 以外の文字(挨拶/説明/コードフェンス/マークダウン)を前後に一切出さない。\n\n"
	"役割：既存の旅行プランとユーザーからのメッセージを基に、当日の状況に応じたアドバイスや代案を提供する。\n\n"
	"入力構造：\n1) travel_plan: 既存の旅行プランJSON\n2) user_message: ユーザーからの質問やリクエスト\n3) current_context: 現在地、時刻、天気などの文脈情報（オプション）\n\n"
	"出力スキーマ（単一JSON）:\n{\n  \"response_type\": \"advice|alternative|information|emergency\",\n  \"message\": string,\n  \"suggestions\": [\n    {\n      \"type\": \"location|timing|activity|route\",\n      \"title\": string,\n      \"description\": string,\n      \"priority\": \"high|medium|low\",\n      \"estimated_time\": string|null,\n      \"location\": {\n        \"name\": string,\n        \"lat\": number|null,\n        \"lng\": number|null\n      }|null\n    }\n  ],\n  \"updated_schedule\": [\n    {\n      \"time\": \"HH:MM\",\n      \"activity\": string,\n      \"location\": string,\n      \"notes\": string|null\n    }\n  ]|null,\n  \"route_info\": {\n    \"origin\": string,\n    \"destination\": string,\n    \"waypoints\": [string],\n    \"mode\": \"driving|walking|bicycling|transit\",\n    \"estimated_duration\": string|null\n  }|null\n}\n\n"
	"対応シナリオ：\n- 天候変化による屋内代替案提案\n- 交通遅延時の時間調整アドバイス\n- 現在地からの最適ルート案内\n- 営業時間・混雑状況の確認と代案\n- 緊急時のサポート情報提供\n- 地域のリアルタイム情報収集\n\n"
	"制約：\n- message は200文字以内で簡潔に\n- suggestions は最大5件まで\n- 安全性を最優先し、危険な提案は行わない\n- 実在する施設・ルートのみ提案\n- 営業時間・定休日を考慮した提案\n\n"
	"Maps情報の取得：Google Maps の地図データ（ジオコーディング/リバースジオコード/場所検索/場所詳細/距離行列/経路案内/標高 など）が必要な場合は、transfer_to_agent(agent_name='googlemapmcp') を呼び出して必要情報を取得し、その結果を要約・検証してあなた自身の最終JSONスキーマに統合すること（サブエージェントの生JSONは貼り付けない）。\n\n"
	"出力は開始文字 '{' から終了 '}' までの 1 個の JSON オブジェクトのみ。コードフェンス、説明文、マークダウンは禁止。"
)

# Define the travel advisor sub-agent
try:
	travel_advisor_agent = LlmAgent(
		name="travel_advisor",
		model=MODEL,
		description="Provide day-of travel assistance and real-time advice based on travel plans and current situation",
		instruction=TRAVEL_ADVISOR_INSTRUCTION,
		sub_agents=[],
		tools=[google_search],
	)
	log.info(f"Travel Advisor Agent initialized with tools")
except Exception as e:
	log.error(f"Failed to initialize Travel Advisor Agent: {e}")
	raise