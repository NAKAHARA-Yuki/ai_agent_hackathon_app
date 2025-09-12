import os
import sys
import logging
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


log = logging.getLogger("agent.googlemapmcp")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
log.info(f"Google Maps MCP Agent model: {MODEL}")

google_maps_api_key = os.getenv("VITE_GOOGLE_MAPS_API_KEY")
print("Google Maps API Key:", google_maps_api_key)

GOOGLEMAP_MCP_INSTRUCTION = (
    "あなたはGoogle Maps API の MCP サーバーを用いて地理情報を取得する専門サブエージェントです。必ず JSON オブジェクト 1 個【のみ】を出力し、前後に説明/コードフェンス/マークダウンは出さない。\n\n"
    "利用可能なアクション（maps_mcp_call の action 引数で指定）：\n"
    "- maps_geocode: 住所→座標（params={address:string})\n"
    "- maps_reverse_geocode: 座標→住所（params={latitude:number, longitude:number})\n"
    "- maps_search_places: テキスト検索（params={query:string, location?:{latitude:number, longitude:number}, radius?:number})\n"
    "- maps_place_details: 場所の詳細（params={place_id:string})\n"
    "- maps_distance_matrix: 距離/時間（params={origins:string[], destinations:string[], mode?:'driving'|'walking'|'bicycling'|'transit'})\n"
    "- maps_elevation: 標高データ（params={locations:Array[{latitude:number, longitude:number}]})\n"
    "- maps_directions: ルート案内（params={origin:string, destination:string, mode?:'driving'|'walking'|'bicycling'|'transit'})\n\n"
    "指示：\n- 適切な action と params を選び、maps_mcp_call を1回で完結に呼び出すこと。\n- 返ってきたJSONを整理して、下記のスキーマに沿って返すこと。\n\n"
    "出力スキーマ（単一JSON）:\n{\n  \"action\": string,\n  \"inputs\": object,\n  \"results\": object|array,\n  \"notes\": string|null\n}\n\n"
    "制約：\n- 不明点は notes に簡潔に記述（最大200文字）\n- action/inputs は実際に呼び出した内容を正確に反映\n"
)

try:
    googlemapmcp_agent = LlmAgent(
        name="googlemapmcp",
        model=MODEL,
        description="Search and summarize Google Maps Platform docs via MCP",
        instruction=GOOGLEMAP_MCP_INSTRUCTION,
        tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params = StdioServerParameters(
                    command='npx',
                    args=[
                        "-y",
                        "@modelcontextprotocol/server-google-maps",
                    ],
                    # Pass the API key as an environment variable to the npx process
                    # This is how the MCP server for Google Maps expects the key.
                    env={
                        "GOOGLE_MAPS_API_KEY": google_maps_api_key
                    }
                ),
            ),
            # You can filter for specific Maps tools if needed:
            # tool_filter=['get_directions', 'find_place_by_id']
        )
    ],
    )
    log.info(f"Google Maps MCP Agent initialized with tools")
except Exception as e:
    log.error(f"Failed to initialize Google Maps MCP Agent: {e}")
    raise
