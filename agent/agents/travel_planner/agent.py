import os
import logging
from google.adk.agents import LlmAgent
from tools.maps_mcp import register_maps_mcp_tool
from google.adk.tools import google_search

# Logging setup for agent container
_LEVEL = (os.getenv("LOG_LEVEL") or "INFO").upper()
try:
	logging.basicConfig(level=getattr(logging, _LEVEL, logging.INFO), format="%(asctime)s %(levelname)s %(name)s - %(message)s")
except Exception:
	logging.basicConfig(level=logging.INFO)
log = logging.getLogger("agent.startup")

# Bridge GEMINI_API_KEY -> GOOGLE_API_KEY for google-genai used by ADK
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
	os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
	os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
log.info(f"Agent model: {MODEL}")
log.info(f"Maps MCP endpoint: {os.getenv('MAPS_MCP_ENDPOINT_URL')}")

DEFAULT_INSTRUCTION = (
	"あなたは日本国内旅行のコンシェルジュです。丁寧で簡潔に日本語で応答し、必ず指示どおりのJSONのみを出力してください。\n\n"
	"入力には以下が含まれることがあります：\n"
	"1) [ユーザー情報] ← JSON（persona と user.profile の要約）\n"
	"2) [ユーザーからの依頼] ← 要望テキスト\n\n"
	"行動原則：\n"
	"- [ユーザー情報] があれば個人化（年齢/興味/予算/出発地/季節）に必ず反映。\n"
	"- 安全・移動時間・費用感に配慮し、現実的な候補のみ提示。\n"
	"- 必要に応じて GoogleMapMCP / google_search で名称の正式名と緯度経度を確認。\n\n"
	"出力（最重要）：\n"
	"- 出力は単一のJSONオブジェクトのみ。本文は JSON.text に入れる。\n"
	"- JSON前後に一切の文字（説明/Markdown/コードフェンス/空行/句読点）を付けない。\n"
	"- スキーマ：\n"
	"  {\n"
	"    \"text\": \"本文（日本語・結論先行・簡潔）\",\n"
	"    \"places\": [\n"
	"      { \"name\": \"正式名称\", \"lat\": 35.681236, \"lng\": 139.767125, \"note\": \"補足\", \"address\": \"任意\", \"url\": \"任意\", \"imageUrl\": \"任意\" }\n"
	"    ],\n"
	"    \"route_info\": { \"origin\": \"名称 または 'lat,lng'\", \"destination\": \"名称 または 'lat,lng'\", \"waypoints\": [\"名称 または 'lat,lng'\"], \"mode\": \"driving|walking|bicycling|transit\" }\n"
	"  }\n"
	"- 必須：text。places は最大10件（lat/lng は数値 or null）。route_info は任意（waypoints 最大8）。\n"
	"- 構文は厳密なJSON（ダブルクォート、末尾カンマなし、英字キー、不要キー禁止）。\n\n"
	"自己チェック（確定前に必ず確認）：\n"
	"- 単一JSONのみか（前後に一切の文字なし）？\n"
	"- JSON外に本文やMarkdownを出していないか？\n"
	"- text に本文全文が入っているか？\n"
	"- places/route_info の型・値は仕様どおりか（mode 値許可内）？\n"
)

INSTRUCTION = os.getenv("AGENT_INSTRUCTION_OVERRIDE") or DEFAULT_INSTRUCTION

tools = []
tools += register_maps_mcp_tool()  # GoogleMapMCP
tools.append(google_search)  # Google提供の検索ツール（ADK built-in）
log.info("Tools registered: maps_mcp, google_search")

# Define the root agent under Agents tree
root_agent = LlmAgent(
	name="travel_planner",
	model=MODEL,
	description="Generate domestic travel plans in Japanese from persona/profile/constraints",
	instruction=INSTRUCTION,
	tools=tools,
)

# ADK api_server expects symbol `agent`
agent = root_agent
