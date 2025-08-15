import os
import logging
from typing import Any
from google.adk.agents import LlmAgent
import httpx
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
	"- text には GitHub Flavored Markdown (GFM) を用いてよい（見出し・箇条書き・表・チェックボックス）。\n"
	"- 比較・日程・料金などは表にまとめることを優先する（Markdownのパイプ区切りテーブルを使用）。\n"
	"- 日程表の推奨列: アイコン | 時間 | 予定 | 詳細 | [任意列(場所/費用/備考など)]。\n"
	"- JSON前後に一切の文字（説明/Markdown/コードフェンス/空行/句読点）を付けない。\n"
	"- スキーマ：\n"
	"  {\n"
	"    \"text\": \"本文（日本語・結論先行・簡潔）。GFMの表を活用可。\",\n"
	"    \"places\": [\n"
	"      { \"name\": \"正式名称\", \"lat\": 35.681236, \"lng\": 139.767125, \"note\": \"補足\", \"address\": \"任意\", \"url\": \"任意\", \"imageUrl\": \"任意\" }\n"
	"    ],\n"
	"    \"route_info\": { \"origin\": \"名称 または 'lat,lng'\", \"destination\": \"名称 または 'lat,lng'\", \"waypoints\": [\"名称 または 'lat,lng'\"], \"mode\": \"driving|walking|bicycling|transit\" }\n"
	"  }\n"
	"- 必須：text。places は最大10件（lat/lng は数値 or null）。route_info は任意（waypoints 最大8）。\n"
	"- 表は横スクロール前提だが5〜6列程度に抑える。1列目は項目名/日付/場所など分かりやすいキーにし、ヘッダー行を付ける。\n"
	"- 構文は厳密なJSON（ダブルクォート、末尾カンマなし、英字キー、不要キー禁止）。\n\n"
	"自己チェック（確定前に必ず確認）：\n"
	"- 単一JSONのみか（前後に一切の文字なし）？\n"
	"- JSON外に本文やMarkdownを出していないか？\n"
	"- text に本文全文が入っているか（表を含む）？\n"
	"- places/route_info の型・値は仕様どおりか（mode 値許可内）？\n"
	"\n[保存に関して]\n"
	"- ユーザーが『保存して』等を明示し、かつ入力中に [SAVE_TOKEN] が付与されている場合のみ、tool `save_travel_plan` を一度だけ呼び出す。\n"
	"- 引数は {token: SAVE_TOKEN, title: 適切な題名, text: JSON.text, places, route_info}。\n"
	"- トークンが無い場合は保存を試みない。\n"
)

INSTRUCTION = os.getenv("AGENT_INSTRUCTION_OVERRIDE") or DEFAULT_INSTRUCTION

tools = []
tools += register_maps_mcp_tool()  # GoogleMapMCP
tools.append(google_search)  # Google提供の検索ツール（ADK built-in）
SERVER_BASE = os.getenv('APP_SERVER_BASE')  # e.g., http://server:8080 or public URL

async def save_travel_plan(token: str, text: str, title: str = "", places: list[dict[str, Any]] = [], route_info: dict[str, Any] = {}) -> dict:
	"""ユーザーの明示同意トークンと共に旅行プランをサーバーに保存する。

	必須:
	- token: サーバーが発行した短期JWTトークン（[SAVE_TOKEN]）。
	- text: 本文（JSON.text）。

	任意:
	- title: 題名（未指定なら空文字）
	- places: 場所配列（例: [{"name": "", "lat": 35.6, "lng": 139.7, "note": "", "address": "", "url": "", "imageUrl": ""}]）
	- route_info: ルート情報（例: {"origin": "", "destination": "", "waypoints": [""], "mode": "driving|walking|bicycling|transit"}）
	"""
	if not SERVER_BASE:
		return {"status": "error", "message": "server_base_not_configured"}
	try:
		async with httpx.AsyncClient(timeout=15.0) as client:
			resp = await client.post(
				SERVER_BASE.rstrip('/') + '/api/plans/by-token',
				json={
					"token": token,
					"title": title,
					"text": text,
					"places": places,
					"route_info": route_info
				},
				headers={"Content-Type": "application/json"}
			)
		if 200 <= resp.status_code < 300:
			data = resp.json()
			data.setdefault("status", "ok")
			return data
		return {"status": "error", "code": resp.status_code, "body": resp.text[:500]}
	except Exception as e:
		return {"status": "error", "message": str(e)}

tools.append(save_travel_plan)
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
