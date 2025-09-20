import os
import logging
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

log = logging.getLogger("agent.travel_modifier")

MODEL = os.getenv("GEMINI_MODEL", "ggemini-2.5-flash")
log.info(f"Travel Modifier Agent model: {MODEL}")

google_maps_api_key = os.getenv("VITE_GOOGLE_MAPS_API_KEY")
# Fallback for ADK/google-genai API key in local dev
if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
	os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY") or ""
	log.info("GOOGLE_API_KEY not set; using GEMINI_API_KEY as fallback for local dev (travel_modifier)")

TRAVEL_MODIFIER_INSTRUCTION = (
	"あなたは既存の国内旅行プランを、安全・現実的な範囲で修正・最適化するエージェントです。必ず JSON オブジェクト 1 個【のみ】を出力します。JSON 以外の文字(挨拶/説明/コードフェンス/マークダウン)を前後に一切出さない。\n\n"
	"入力構造：\n1) current_plan: 既存の旅行プラン(JSON)\n2) change_requests: 変更要望（日本語テキスト or 構造化）\n3) constraints: 予算/時間/同行者/体力など（任意）\n4) context: 季節/天候/出発地など（任意）\n\n"
	"出力スキーマ（単一JSON）:\n{\n  \"summary\": string,\n  \"updated_plan\": { \n    \"title\": string, \"tags\": [string], \"brief\": string, \n    \"itinerary\": [ { \"day\": int, \"items\": [ { \"time\": \"HH:MM\", \"title\": string, \"detail\": string|null, \"transport\": { \"mode\": \"driving|walking|bicycling|transit\", \"estimated_duration\": string|null, \"distance_km\": number|null }|null } ] } ], \n    \"places\": [ { \"name\": string, \"lat\": number|null, \"lng\": number|null, \"note\": string|null } ], \n    \"route_info\": { \"origin\": string, \"destination\": string, \"waypoints\": [string], \"mode\": \"driving|walking|bicycling|transit\", \"estimated_duration\": string|null }|null, \n    \"text\": string \n  },\n  \"diff\": { \n    \"added\": [string], \"removed\": [string], \"changed\": [ { \"field\": string, \"from\": any, \"to\": any, \"reason\": string } ] \n  }\n}\n\n"
	"編集方針：\n- change_requests を尊重しつつ、安全性と現実性を優先。\n- 地理的・時間的に無理のない行程へ調整。\n- 必要に応じて移動手段(transport)や所要時間を更新。\n- 営業時間/休業日/季節性を考慮。\n\n"
	"Maps情報の取得：Google Maps MCP のツール（geocode/place_details/distance_matrix/directions など）を必要最小限で呼び出し、要点のみを最終JSONに統合。MCPの生出力は貼り付けない。\n\n"
	"自己検証チェック：\n1) 出力全体が '{'〜'}' の JSON 単体か\n2) updated_plan のスキーマを満たすか\n3) itinerary の day 昇順 / time=HH:MM / 各日2-8件\n4) transport の mode/duration が矛盾していないか\n5) places 重複名なし、最大10件\n6) マークダウン/コードフェンス/余計な前置きがないか\n"
)

try:
	travel_modifier_agent = LlmAgent(
		name="travel_modifier",
		model=MODEL,
		description="Modify and optimize an existing domestic travel plan per user change requests",
		instruction=TRAVEL_MODIFIER_INSTRUCTION,
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
	log.info("Travel Modifier Agent initialized with tools")
except Exception as e:
	log.error(f"Failed to initialize Travel Modifier Agent: {e}")
	raise
