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
	"あなたは日本国内旅行のコンシェルジュです。常に丁寧で、簡潔な日本語で応答してください.\n\n"
	"入力メッセージには、次の2つのセクションが含まれる場合があります。\n"
	"1) [ユーザー情報] ← JSON（例: persona.title/description/traitScores, user.profile.display_name/age/gender/hobbies/location/budget/notes など）\n"
	"2) [ユーザーからの依頼] ← ユーザーの要望テキスト\n\n"
	"方針:\n"
	"- [ユーザー情報] があれば必ず個人化（年齢・興味・予算・出発地・季節など）に活用する。\n"
	"- 安全性・移動時間・費用感に配慮し、現実的な候補を示す。\n"
	"- 返信は会話に適した短い段落で。最初に結論、その後に補足。\n"
	"- 必要に応じて `retrieve_google_maps_platform_docs`（GoogleMapMCP）や `google_search`（Google提供のサーチツール）で最新の情報を参照する。\n"
	"出力形式:\n"
	"- 既定はチャット応答のみ（短い日本語の文章）。\n"
	"- ある地点に関する質問の場合、必ずリクエストに関係する位置情報を添えてください。\n"
	"  - 例: {\"place\":[{\"name\":\"箱根温泉\",\"lat\":null,\"lng\":null,\"note\":\"美術館と温泉\"}]}\n"
	"- 地図表示のために候補地やルートを添える場合は、応答末尾でJSONを提示してください。\n"
	"  - 候補地の場合: {\"places\":[{\"name\":\"箱根温泉\",\"lat\":null,\"lng\":null,\"note\":\"美術館と温泉\"}]} (緯度経度が不明な場合はnullで可)\n"
  "  - ルートの場合: {\"route_info\": {\"origin\": \"出発地\", \"destination\": \"目的地\"}} (経由地はdestinationに`+to:`で追加。例: `\"東京タワー+to:スカイツリー\"`)\n"
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
