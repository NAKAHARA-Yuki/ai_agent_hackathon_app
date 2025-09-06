import os
import logging
import sys
from typing import Any
from google.adk.agents import LlmAgent
import httpx
from tools.maps_mcp import register_maps_mcp_tool
from google.adk.tools import google_search

# 共有モジュール(shared/logging_config.py)は本コンテナにコピーしない方針のため
# インポートに失敗した場合は最小限のフォールバックを内蔵定義する。
try:
	sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared'))
	from logging_config import configure_basic_cloud_logging, enforce_single_line_all  # type: ignore
except Exception:  # shared が無い/壊れている場合
	class _SingleLineFormatter(logging.Formatter):
		def format(self, record: logging.LogRecord) -> str:  # noqa: D401
			msg = super().format(record)
			return ' '.join(msg.replace('\n', ' ').replace('\r', ' ').split())

	def _base_handler(level: str):
		h = logging.StreamHandler()
		h.setFormatter(_SingleLineFormatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s'))
		h.setLevel(level)
		return h

	def configure_basic_cloud_logging(level_name: str = 'INFO', force: bool = False):  # minimal互換
		lvl = getattr(logging, (level_name or 'INFO').upper(), logging.INFO)
		root = logging.getLogger()
		if force:
			for h in list(root.handlers):
				root.removeHandler(h)
		if not root.handlers:
			root.addHandler(_base_handler(lvl))
		root.setLevel(lvl)
		return root

	def enforce_single_line_all(level: str = 'INFO'):
		lvl = getattr(logging, (level or 'INFO').upper(), logging.INFO)
		root = logging.getLogger()
		for h in root.handlers:
			h.setFormatter(_SingleLineFormatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s'))
			h.setLevel(lvl)
		root.setLevel(lvl)

# Cloud-friendly logging setup for agent container
_LEVEL = (os.getenv("LOG_LEVEL") or "INFO").upper()
try:
	configure_basic_cloud_logging(level_name=_LEVEL, force=True)
	enforce_single_line_all(_LEVEL)
except Exception:
	configure_basic_cloud_logging(level_name="INFO", force=True)
	try:
		enforce_single_line_all(_LEVEL)
	except Exception:
		pass
log = logging.getLogger("agent.startup")

# Bridge GEMINI_API_KEY -> GOOGLE_API_KEY for google-genai used by ADK
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
	os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
	os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
log.info(f"Agent model: {MODEL}")
log.info(f"Maps MCP endpoint: {os.getenv('MAPS_MCP_ENDPOINT_URL')}")

DEFAULT_INSTRUCTION = (
	"あなたは日本国内旅行のコンシェルジュです。必ず JSON 1 個のみを出力し、3 つの完全な旅行計画を含めます (前後に余計な文字・コードフェンス禁止)。\n\n"
	"入力構造：\n1) persona/profile 要約 JSON\n2) ユーザー依頼キーワード\n\n"
	"目標：利用者の興味/制約を反映し、選択可能な 3 案 (各: タイトル/タグ/短い説明/日別行程/主要スポット/任意ルート) を提示。地理的合理性と季節感・移動時間を考慮。危険/非現実/閉鎖施設除外。\n\n"
	"出力仕様（単一JSON）:\n{\n  \"summary\": \"全体要約 1-2文\",\n  \"plans\": [\n    { \"title\": \"案1タイトル\", \"tags\": [\"温泉\", \"自然\"], \"brief\": \"40字以内説明\", \"itinerary\": [ { \"day\":1, \"items\":[ {\"time\":\"09:00\", \"title\":\"スポット\", \"detail\":\"任意説明\"} ] } ], \"places\": [ { \"name\": \"正式名称\", \"lat\":35.0, \"lng\":139.0, \"note\":\"任意\" } ], \"route_info\": { \"origin\": \"名称 or 'lat,lng'\", \"destination\": \"名称 or 'lat,lng'\", \"waypoints\": [], \"mode\": \"driving|walking|bicycling|transit\" }, \"text\": \"GFM本文(概要/日別表)\" },\n    { \"title\": \"案2タイトル\", \"tags\": [\"文化\"], \"brief\": \"説明\", \"itinerary\": [], \"places\": [], \"route_info\": null, \"text\": \"...\" },\n    { \"title\": \"案3タイトル\", \"tags\": [\"グルメ\"], \"brief\": \"説明\", \"itinerary\": [], \"places\": [], \"route_info\": null, \"text\": \"...\" }\n  ]\n}\n\n"
	"制約：\n- plans は必ず 3 件。title 25文字以内。tags 各 1-6 語。brief 40字以内。\n- itinerary: day 昇順 / time=HH:MM / 1日 2-8 items。\n- 各 plan の places 最大10 (重複名除外)。lat/lng 数値 or null。\n- route_info 任意。\n- text は該当プラン説明 + 簡潔日別表 (Markdown) を含め JSON 外へ書かない。\n- 余計なキー/末尾カンマ/シングルクォート禁止。\n\n"
	"自己検証チェックリスト：\n1) JSON 1 個のみか?\n2) plans 配列 3 件か?\n3) 各 plan 必須キー (title,tags,brief,itinerary,places,text) あるか?\n4) 時刻形式/ day 順序 / items 数制約守るか?\n5) 不正/危険/閉鎖スポット含んでいないか?\n6) 前後に文字やコードフェンス無しか?\n\n"
	"出力は開始文字 '{' から終了 '}' までの 1 個の JSON オブジェクトのみ。``` や説明文, マークダウン, 前後のテキストは禁止。"
)

INSTRUCTION = os.getenv("AGENT_INSTRUCTION_OVERRIDE") or DEFAULT_INSTRUCTION

tools = []
tools += register_maps_mcp_tool()  # GoogleMapMCP
tools.append(google_search)  # Google提供の検索ツール（ADK built-in）
SERVER_BASE = os.getenv('APP_SERVER_BASE')  # e.g., http://server:8080 or public URL

log.info("Tools registered: maps_mcp, google_search (保存ツール無効化)")

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
