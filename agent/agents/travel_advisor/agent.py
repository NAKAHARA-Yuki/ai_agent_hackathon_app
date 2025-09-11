import os
import logging
import sys
from typing import Any
from google.adk.agents import LlmAgent
import httpx

# Import tools with better error handling
try:
    # Try relative import first
    from ...tools.maps_mcp import register_maps_mcp_tool
except ImportError:
    # Fallback to adding parent directory to path
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from tools.maps_mcp import register_maps_mcp_tool

try:
    from google.adk.tools import google_search
except ImportError as e:
    log.warning(f"Failed to import google_search tool: {e}")
    google_search = None

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
log = logging.getLogger("agent.travel_advisor")

# Bridge GEMINI_API_KEY -> GOOGLE_API_KEY for google-genai used by ADK
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
	os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
	os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
log.info(f"Travel Advisor Agent model: {MODEL}")

TRAVEL_ADVISOR_INSTRUCTION = (
	"あなたは旅行当日サポート専門のAIアドバイザーです。必ず JSON オブジェクト 1 個【のみ】を出力します。JSON 以外の文字(挨拶/説明/コードフェンス/マークダウン)を前後に一切出さない。\n\n"
	"役割：既存の旅行プランとユーザーからのメッセージを基に、当日の状況に応じたアドバイスや代案を提供する。\n\n"
	"入力構造：\n1) travel_plan: 既存の旅行プランJSON\n2) user_message: ユーザーからの質問やリクエスト\n3) current_context: 現在地、時刻、天気などの文脈情報（オプション）\n\n"
	"出力スキーマ（単一JSON）:\n{\n  \"response_type\": \"advice|alternative|information|emergency\",\n  \"message\": string,\n  \"suggestions\": [\n    {\n      \"type\": \"location|timing|activity|route\",\n      \"title\": string,\n      \"description\": string,\n      \"priority\": \"high|medium|low\",\n      \"estimated_time\": string|null,\n      \"location\": {\n        \"name\": string,\n        \"lat\": number|null,\n        \"lng\": number|null\n      }|null\n    }\n  ],\n  \"updated_schedule\": [\n    {\n      \"time\": \"HH:MM\",\n      \"activity\": string,\n      \"location\": string,\n      \"notes\": string|null\n    }\n  ]|null,\n  \"route_info\": {\n    \"origin\": string,\n    \"destination\": string,\n    \"waypoints\": [string],\n    \"mode\": \"driving|walking|bicycling|transit\",\n    \"estimated_duration\": string|null\n  }|null\n}\n\n"
	"対応シナリオ：\n- 天候変化による屋内代替案提案\n- 交通遅延時の時間調整アドバイス\n- 現在地からの最適ルート案内\n- 営業時間・混雑状況の確認と代案\n- 緊急時のサポート情報提供\n- 地域のリアルタイム情報収集\n\n"
	"制約：\n- message は200文字以内で簡潔に\n- suggestions は最大5件まで\n- 安全性を最優先し、危険な提案は行わない\n- 実在する施設・ルートのみ提案\n- 営業時間・定休日を考慮した提案\n\n"
	"出力は開始文字 '{' から終了 '}' までの 1 個の JSON オブジェクトのみ。コードフェンス、説明文、マークダウンは禁止。"
)

tools = []
try:
    tools += register_maps_mcp_tool()  # GoogleMapMCP
    log.info("Maps MCP tool registered successfully")
except Exception as e:
    log.warning(f"Failed to register Maps MCP tool: {e}")

if google_search:
    tools.append(google_search)  # Google提供の検索ツール（ADK built-in）
    log.info("Google search tool registered successfully")
else:
    log.warning("Google search tool not available")

log.info(f"Travel Advisor Sub-Agent: {len(tools)} tools registered")

# Define the travel advisor sub-agent
try:
	travel_advisor_agent = LlmAgent(
		name="travel_advisor",
		model=MODEL,
		description="Provide day-of travel assistance and real-time advice based on travel plans and current situation",
		instruction=TRAVEL_ADVISOR_INSTRUCTION,
		tools=tools,
	)
	log.info(f"Travel Advisor Agent initialized with {len(tools)} tools")
except Exception as e:
	log.error(f"Failed to initialize Travel Advisor Agent: {e}")
	raise