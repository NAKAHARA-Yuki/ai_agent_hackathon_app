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
log = logging.getLogger("agent.travel_planner")

# Bridge GEMINI_API_KEY -> GOOGLE_API_KEY for google-genai used by ADK
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
	os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
	os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
log.info(f"Travel Planner Agent model: {MODEL}")

TRAVEL_PLANNER_INSTRUCTION = (
	"あなたは日本国内旅行のコンシェルジュです。必ず JSON オブジェクト 1 個【のみ】を出力します。3 つの完全な旅行計画を含め、JSON 以外の文字(挨拶/説明/コードフェンス/マークダウン)を前後に一切出さない。\n\n"
	"入力構造：\n1) persona/profile 要約 JSON\n2) ユーザー依頼キーワード\n\n"
	"目標：利用者の興味/制約を反映し、選択可能な 3 案 (各: タイトル/タグ/短い説明/日別行程/主要スポット/任意ルート) を提示。地理的合理性と季節感・移動時間を考慮。危険/非現実/閉鎖施設除外。\n\n"
	"最低限スキーマ（単一JSON）:\n{\n  \"summary\": string,\n  \"plans\": [\n    { \"title\": string, \"tags\": [string], \"brief\": string, \"itinerary\": [ { \"day\": int, \"items\": [ { \"time\": \"HH:MM\", \"title\": string, \"detail\": string|null } ] } ], \"places\": [ { \"name\": string, \"lat\": number|null, \"lng\": number|null, \"note\": string|null } ], \"route_info\": { \"origin\": string, \"destination\": string, \"waypoints\": [string], \"mode\": \"driving|walking|bicycling|transit\" }|null, \"text\": string } , ... (合計3件)\n  ]\n}\n\n"
	"OK例 (単純化): {\"summary\":\"...\",\"plans\":[{\"title\":\"A\",\"tags\":[\"温泉\"],\"brief\":\"説明\",\"itinerary\":[{\"day\":1,\"items\":[{\"time\":\"09:00\",\"title\":\"スポット\"}]}],\"places\":[{\"name\":\"場所1\",\"lat\":35.0,\"lng\":139.0,\"note\":null}],\"route_info\":null,\"text\":\"...\"}, {...},{...}]}\n"
	"NG例: '以下にプランを示します:' など JSON 以外の前置き / ```json フェンス / 単数 plan / 途中で説明文を JSON の外に記述 / シングルクォート利用。\n\n"
	"制約：\n- plans は必ず 3 件。title 25文字以内。tags 各 1-6 語。brief 40字以内。\n- itinerary: day 昇順 / time=HH:MM / 1日 2-8 items。\n- 各 plan の places 最大10 (重複名除外)。lat/lng 数値 or null。\n- route_info 任意。\n- text はプレーンな説明文章のみ (Markdown記法・表・見出し禁止)。\n- 余計なキー/末尾カンマ/シングルクォート禁止。\n\n"
	"自己検証チェックリスト：\n1) 出力全体が '{' で始まり '}' で終わるか (前後空白以外なし)\n2) plans が配列で長さ=3 か\n3) 各 plan に title,tags,brief,itinerary,places,text が存在し型正しいか\n4) itinerary の time が HH:MM 形式か / day 昇順か / items 数 2-8 か\n5) places の name 重複なし & 最大10 件か\n6) コードフェンス/説明文/余計な文字列が JSON 外に出ていないか\n7) text に Markdown (# * | ``` 等) が含まれていないか\n\n"
	"出力は開始文字 '{' から終了 '}' までの 1 個の JSON オブジェクトのみ。``` や説明文, マークダウン, 前後のテキストは禁止。\n"
	"(EN Warning) Output exactly ONE raw JSON object only. No markdown headings/tables/fences. Any extra text may cause rejection."
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

log.info(f"Travel Planner Sub-Agent: {len(tools)} tools registered")

# Define the travel planner sub-agent
try:
	travel_planner_agent = LlmAgent(
		name="travel_planner",
		model=MODEL,
		description="Generate domestic travel plans in Japanese from persona/profile/constraints",
		instruction=TRAVEL_PLANNER_INSTRUCTION,
		tools=tools,
	)
	log.info(f"Travel Planner Agent initialized with {len(tools)} tools")
except Exception as e:
	log.error(f"Failed to initialize Travel Planner Agent: {e}")
	raise

# Also expose the root_agent from root_coordinator for ADK agent loader
# This ensures all possible import paths work: travel_planner.agent.root_agent and travel_planner.root_agent

# Set root_agent to None initially to avoid circular import during module loading
root_agent = None

def _load_root_agent():
	"""Load root_agent after all modules are initialized."""
	global root_agent
	if root_agent is None:
		try:
			# Import after travel_planner_agent is created to avoid circular imports
			import sys
			import os
			sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
			from root_coordinator.agent import root_agent as imported_root_agent
			root_agent = imported_root_agent
			log.info("root_agent loaded successfully in travel_planner.agent module")
		except ImportError as e:
			log.warning(f"Could not load root_agent in agent module: {e}")
			root_agent = None
	return root_agent

# Try to load root_agent immediately if possible
try:
	_load_root_agent()
except:
	pass  # Will be None and can be loaded later
