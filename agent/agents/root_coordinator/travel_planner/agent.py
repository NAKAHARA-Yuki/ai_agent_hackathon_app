import os
import sys
import logging
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
log = logging.getLogger("agent.travel_planner")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
log.info(f"Travel Planner Agent model: {MODEL}")

google_maps_api_key = os.getenv("VITE_GOOGLE_MAPS_API_KEY")
# Fallback for ADK/google-genai: expose GEMINI_API_KEY as GOOGLE_API_KEY when missing (local dev)
if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
	os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY") or ""
	log.info("GOOGLE_API_KEY not set; using GEMINI_API_KEY as fallback for local dev (travel_planner)")
print("Google Maps API Key:", google_maps_api_key)

TRAVEL_PLANNER_INSTRUCTION = (
	"あなたは日本国内旅行のコンシェルジュです。必ず JSON オブジェクト 1 個【のみ】を出力します。3 つの完全な旅行計画を含め、JSON 以外の文字(挨拶/説明/コードフェンス/マークダウン)を前後に一切出さない。\n\n"
	"入力構造：\n1) persona/profile 要約 JSON\n2) ユーザー依頼キーワード\n\n"
	"目標：利用者の興味/制約を反映し、選択可能な 3 案 (各: タイトル/タグ/短い説明/日別行程/主要スポット/任意ルート) を提示。地理的合理性と季節感・移動時間を考慮。危険/非現実/閉鎖施設除外。各行程には可能な限り『移動手段(transport)』と所要時間を含める。\n\n"
	"カテゴリ指定（順序固定・必須）：\n1) 王道プラン — あなたの好みをストレートに反映した、満足間違いなしのプラン。\n2) 発見プラン — あなたがまだ知らない、でもきっと好きになる隠れた名所や体験を提案。\n3) 挑戦プラン — 少しだけ勇気を出して、新しい世界の扉を開く冒険的なプラン。\n\n"
	"最低限スキーマ（単一JSON）：\n{\n  \"summary\": string,\n  \"plans\": [\n    { \"category_label\": \"王道プラン|発見プラン|挑戦プラン\", \"title\": string, \"tags\": [string], \"brief\": string, \"itinerary\": [ { \"day\": int, \"items\": [ { \"time\": \"HH:MM\", \"title\": string, \"detail\": string|null, \"transport\": { \"mode\": \"driving|walking|bicycling|transit\", \"estimated_duration\": string|null, \"distance_km\": number|null }|null } ] } ], \"places\": [ { \"name\": string, \"lat\": number|null, \"lng\": number|null, \"note\": string|null } ], \"route_info\": { \"origin\": string, \"destination\": string, \"waypoints\": [string], \"mode\": \"driving|walking|bicycling|transit\", \"estimated_duration\": string|null }|null, \"text\": string } , ... (合計3件)\n  ]\n}\n\n"
	"OK例 (単純化): {\"summary\":\"...\",\"plans\":[{\"category_label\":\"王道プラン\",\"title\":\"A\",\"tags\":[\"温泉\"],\"brief\":\"説明\",\"itinerary\":[{\"day\":1,\"items\":[{\"time\":\"09:00\",\"title\":\"スポット\",\"transport\":{\"mode\":\"transit\",\"estimated_duration\":\"15分\"}}]}],\"places\":[{\"name\":\"場所1\",\"lat\":35.0,\"lng\":139.0,\"note\":null}],\"route_info\":{\"origin\":\"羽田空港\",\"destination\":\"浅草\",\"waypoints\":[],\"mode\":\"transit\",\"estimated_duration\":\"45分\"},\"text\":\"...\"}, {...},{...}]}\n"
	"NG例: '以下にプランを示します:' など JSON 以外の前置き / ```json フェンス / 単数 plan / 途中で説明文を JSON の外に記述 / シングルクォート利用。\n\n"
	"制約：\n- plans は必ず 3 件（順序：王道→発見→挑戦）。title 25文字以内。tags 各 1-6 語。brief 40字以内。\n- itinerary: day 昇順 / time=HH:MM / 1日 2-8 items。\n- 各 plan の places 最大10 (重複名除外)。lat/lng 数値 or null。\n- route_info 任意。\n- text はプレーンな説明文章のみ (Markdown記法・表・見出し禁止)。\n- 余計なキー/末尾カンマ/シングルクォート禁止。\n\n"
	"移動手段（transport）の記述：\n- 移動が伴う items には可能な限り transport オブジェクトを付与する。\n- transport = { \"mode\": \"driving|walking|bicycling|transit\", \"estimated_duration\": string|null, \"distance_km\": number|null }\n- 長距離徒歩は避け、現実的な移動手段を選択。所要時間が重要な箇所は概算でも良いが、必要に応じて directions/distance matrix で補強。\n\n"
	"Maps情報の取得：このエージェントには Google Maps MCP ツールが接続されています。地図データ（ジオコーディング/リバースジオコード/場所検索/場所詳細/距離行列/経路案内/標高 など）が必要な場合は、MCP の対応ツール（例: geocode / reverse_geocode / search_places / place_details / distance_matrix / directions / elevation など）を必要最小限で呼び出して情報を取得し、要点のみを要約・検証して最終JSONに統合すること。MCP の生出力をそのまま貼り付けない。\n\n"
	"自己検証チェックリスト：\n1) 出力全体が '{' で始まり '}' で終わるか (前後空白以外なし)\n2) plans が配列で長さ=3 か（順序: 王道,発見,挑戦）\n3) 各 plan に category_label,title,tags,brief,itinerary,places,text が存在し型正しいか\n4) itinerary の time が HH:MM 形式か / day 昇順か / items 数 2-8 か\n4.1) 主要な移動箇所に transport.mode と estimated_duration が付与されているか\n5) places の name 重複なし & 最大10 件か\n6) コードフェンス/説明文/余計な文字列が JSON 外に出ていないか\n7) text に Markdown (# * | ``` 等) が含まれていないか\n\n"
	"出力は開始文字 '{' から終了 '}' までの 1 個の JSON オブジェクトのみ。``` や説明文, マークダウン, 前後のテキストは禁止。\n"
	"(EN Warning) Output exactly ONE raw JSON object only. No markdown headings/tables/fences. Any extra text may cause rejection."
)

try:
	travel_planner_agent = LlmAgent(
		name="travel_planner",
		model=MODEL,
		description="Generate domestic travel plans in Japanese from persona/profile/constraints",
		instruction=TRAVEL_PLANNER_INSTRUCTION,
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
	log.info(f"Travel Planner Agent initialized with tools")
except Exception as e:
	log.error(f"Failed to initialize Travel Planner Agent: {e}")
	raise

