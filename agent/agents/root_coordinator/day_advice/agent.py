import os
import logging
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

log = logging.getLogger("agent.day_advice")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
log.info(f"Day Advice Agent model: {MODEL}")

google_maps_api_key = os.getenv("VITE_GOOGLE_MAPS_API_KEY")

DAY_ADVICE_INSTRUCTION = (
	"あなたは旅行当日サポート専用のAIアシスタントです。必ず JSON オブジェクト 1 個【のみ】を出力します。JSON 以外の文字(挨拶/説明/コードフェンス/マークダウン)を前後に一切出さない。\n\n"
	"役割：既存の旅行プラン(travel_plan) と ユーザーのメッセージ(user_message) を基に、現在の状況に応じたアドバイスや代案を提供する。\n\n"
	"入力構造：\n1) travel_plan: 既存の旅行プランJSON\n2) user_message: ユーザーからの質問やリクエスト\n3) current_context: 現在地、時刻、天気などの文脈情報（オプション）\n\n"
	"出力スキーマ（単一JSON）:\n{\n  \"response_type\": \"advice|alternative|information|emergency\",\n  \"message\": string,\n  \"suggestions\": [\n    {\n      \"type\": \"location|timing|activity|route\",\n      \"title\": string,\n      \"description\": string,\n      \"priority\": \"high|medium|low\",\n      \"estimated_time\": string|null,\n      \"location\": {\n        \"name\": string,\n        \"lat\": number|null,\n        \"lng\": number|null\n      }|null\n    }\n  ],\n  \"updated_schedule\": [\n    {\n      \"time\": \"HH:MM\",\n      \"activity\": string,\n      \"location\": string,\n      \"notes\": string|null\n    }\n  ]|null,\n  \"route_info\": {\n    \"origin\": string,\n    \"destination\": string,\n    \"waypoints\": [string],\n    \"mode\": \"driving|walking|bicycling|transit\",\n    \"estimated_duration\": string|null\n  }|null\n}\n\n"
	"対応シナリオ：\n- 天候変化による屋内代替案提案\n- 交通遅延時の時間調整アドバイス\n- 現在地からの最適ルート案内\n- 営業時間・混雑状況の確認と代案\n- 緊急時のサポート情報提供\n\n"
	"制約：\n- message は200文字以内で簡潔に\n- suggestions は最大5件まで\n- 安全性を最優先し、危険な提案は行わない\n- 実在する施設・ルートのみ提案\n- 営業時間・定休日を考慮した提案\n\n"
	"Maps情報の取得：Google Maps の地図データ（ジオコーディング/場所検索/詳細/距離行列/経路案内 など）が必要な場合は、MCP のツールを最小限で呼び出し、要点のみを最終JSONに統合すること（MCPの生出力は貼り付けない）。\n\n"
	"出力は開始文字 '{' から終了 '}' までの 1 個の JSON オブジェクトのみ。コードフェンス、説明文、マークダウンは禁止。"
)

try:
	day_advice_agent = LlmAgent(
		name="day_advice",
		model=MODEL,
		description="Provide day-of travel assistance and real-time advice based on travel plans and current context",
		instruction=DAY_ADVICE_INSTRUCTION,
		sub_agents=[],
		tools=[MCPToolset(
			connection_params=StdioConnectionParams(
				server_params = StdioServerParameters(
					command='npx',
					args=[
						"-y",
						"@modelcontextprotocol/server-google-maps",
					],
					env={
						"GOOGLE_MAPS_API_KEY": google_maps_api_key
					}
				),
				timeout=10,
			),
		)],
	)
	log.info("Day Advice Agent initialized with tools")
except Exception as e:
	log.error(f"Failed to initialize Day Advice Agent: {e}")
	raise
