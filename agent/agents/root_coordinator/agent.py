import os
import logging
import sys
import json
from typing import Any
from google.adk.agents import LlmAgent

# Import sub-agents with better error handling and avoiding circular imports
_travel_planner_agent = None
_travel_advisor_agent = None

def _get_sub_agents():
    """Lazy import sub-agents to avoid circular import issues."""
    global _travel_planner_agent, _travel_advisor_agent
    
    if _travel_planner_agent is None or _travel_advisor_agent is None:
        try:
            # Use absolute imports to avoid confusion
            import sys
            import os
            
            # Add the parent agents directory to path
            agents_dir = os.path.dirname(__file__)
            parent_dir = os.path.dirname(agents_dir)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            
            # Import sub-agents directly from their modules
            travel_planner_module = __import__('travel_planner.agent', fromlist=['travel_planner_agent'])
            _travel_planner_agent = travel_planner_module.travel_planner_agent
            
            travel_advisor_module = __import__('travel_advisor.agent', fromlist=['travel_advisor_agent'])
            _travel_advisor_agent = travel_advisor_module.travel_advisor_agent
            
            log.info("Sub-agents imported successfully")
        except Exception as e:
            log.error(f"Failed to import sub-agents: {e}")
            raise ImportError(f"Could not import required sub-agents: {e}")
    
    return _travel_planner_agent, _travel_advisor_agent

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
log = logging.getLogger("agent.root_coordinator")

# Bridge GEMINI_API_KEY -> GOOGLE_API_KEY for google-genai used by ADK
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
	os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
	os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")  # Use a more stable model variant
log.info(f"Root Coordinator Agent model: {MODEL}")

ROOT_COORDINATOR_INSTRUCTION = (
	"あなたは旅行アシスタントのコーディネーターです。ユーザーのリクエストを分析し、適切なサブエージェントに振り分けます。\n\n"
	"利用可能なサブエージェント：\n"
	"1) travel_planner: 新しい旅行プランの作成。persona/profile情報から3つの旅行プランを生成\n"
	"2) travel_advisor: 旅行当日のサポート。既存のプランと現在の状況に基づいてアドバイスを提供\n\n"
	"判断基準：\n"
	"- 新しい旅行プランの作成依頼 → travel_planner\n"
	"- 既存プランの修正、当日のトラブル対応、リアルタイム情報 → travel_advisor\n"
	"- 判断が困難な場合は travel_planner を選択\n\n"
	"あなたは選択したサブエージェントの応答をそのまま返すことが役割です。レスポンスの形式を変更してはいけません。"
)

# Define the root coordinator agent with sub-agents
try:
	travel_planner_agent, travel_advisor_agent = _get_sub_agents()
	
	root_agent = LlmAgent(
		name="root_coordinator",
		model=MODEL,
		description="Coordinate requests to appropriate sub-agents (travel_planner or travel_advisor)",
		instruction=ROOT_COORDINATOR_INSTRUCTION,
		sub_agents=[
			travel_planner_agent,
			travel_advisor_agent
		],
		tools=[],  # Root agent doesn't need direct tools, sub-agents handle them
	)
	log.info("Root Coordinator Agent initialized with travel_planner and travel_advisor sub-agents")
except Exception as e:
	log.error(f"Failed to initialize Root Coordinator Agent: {e}")
	raise