import os
import logging
from google.adk.agents import LlmAgent
# Tools
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
# from google.adk.tools import google_search   # type: ignore

log = logging.getLogger("agent.general_chat")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
log.info(f"General Chat Agent model: {MODEL}")

google_maps_api_key = os.getenv("VITE_GOOGLE_MAPS_API_KEY")
print("Google Maps API Key:", google_maps_api_key)

# Fallback for ADK/google-genai API key in local dev
if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY") or ""
    log.info("GOOGLE_API_KEY not set; using GEMINI_API_KEY as fallback for local dev (general_chat)")

GENERAL_CHAT_INSTRUCTION = (
    "あなたは一般的な旅行相談と位置情報に基づく案内を行う旅行アシスタントです。必ず JSON オブジェクト 1 個【のみ】を出力します。JSON 以外の文字(挨拶/説明/コードフェンス/マークダウン)を前後に一切出さない。\n\n"
    "役割:\n"
    "- 現在位置やユーザー質問に基づき、観光スポット/飲食店/施設/移動案内/注意喚起などを日本語で案内する。\n"
    "- 不明点は無理に断定せず、調べ方の提案も行う。\n\n"
    "位置情報が提供された場合:\n"
    "- 必要に応じて地図データ (Google Maps MCP ツール) を使用し、必要情報を取得・要約して統合する。\n"
    "- 具体的な場所名、住所、営業時間、口コミ/評価、所要時間などの実用情報を含める（place_details 等で取得可能な範囲）。\n"
    "- 徒歩/電車/バス/自転車など現実的な移動手段と概算時間を併記。\n\n"
    "出力スキーマ（単一JSON）:\n"
    "{\n"
    "  \"response_type\": \"information|recommendation|route|warning\",\n"
    "  \"message\": string,\n"
    "  \"suggestions\": [\n"
    "    { \"type\": \"place|food|route|tip\", \"title\": string, \"description\": string, \"priority\": \"high|medium|low\", \"estimated_time\": string|null, \"location\": { \"name\": string, \"lat\": number|null, \"lng\": number|null }|null }\n"
    "  ],\n"
    "  \"places\": [ { \"name\": string, \"lat\": number|null, \"lng\": number|null, \"address\": string|null, \"opening_hours\": string|null, \"rating\": number|null } ],\n"
    "  \"route_info\": { \"origin\": string, \"destination\": string, \"waypoints\": [string], \"mode\": \"driving|walking|bicycling|transit\", \"estimated_duration\": string|null }|null\n"
    "}\n\n"
    "Maps情報の取得：Google Maps MCP のツール（geocode/search_places/place_details/distance_matrix/directions 等）を必要最小限で呼び出し、要点のみを最終JSONに統合。MCP の生出力は貼り付けない。\n\n"
    "自己検証チェック：\n"
    "1) 出力全体が '{'〜'}' の JSON 単体か（前後に説明/コードフェンスなし）\n"
    "2) response_type と message が存在し、型が正しいか\n"
    "3) suggestions は最大5件、各フィールドの型が正しいか\n"
    "4) places の name 重複なし、最大10件、lat/lng は数値か null か\n"
    "5) route_info がある場合、mode と estimated_duration が矛盾していないか\n\n"
    "出力は開始文字 '{' から終了 '}' までの 1 個の JSON オブジェクトのみ。コードフェンス、説明文、マークダウンは禁止。\n"
    "(EN Warning) Output exactly ONE raw JSON object only. No markdown headings/tables/fences. Any extra text may cause rejection."
)

# Initialize tools - using Google Search for real-time location info
# Create the general chat agent
general_chat_agent = LlmAgent(
    name="general_chat",
    model=MODEL,
    description="General travel chat agent with location-based assistance using Google Maps and search",
    instruction=GENERAL_CHAT_INSTRUCTION,
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

log.info(f"General Chat Agent initialized with {len(general_chat_agent.tools)} tool(s)")