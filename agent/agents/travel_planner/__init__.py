# Travel Planner Sub-Agent and Root Agent Exposure
from .agent import travel_planner_agent

# Create root_agent by importing the coordinator components directly
# This avoids circular import issues by creating the root agent here
def _create_root_agent():
    """Create the root agent directly to avoid circular import issues."""
    try:
        import os
        import logging
        from google.adk.agents import LlmAgent
        
        # Import sub-agents directly
        from .agent import travel_planner_agent as tp_agent
        
        # Import travel advisor agent
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from travel_advisor.agent import travel_advisor_agent as ta_agent
        
        # Create root coordinator agent directly here
        MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        
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
        
        root_agent = LlmAgent(
            name="root_coordinator",
            model=MODEL,
            description="Coordinate requests to appropriate sub-agents (travel_planner or travel_advisor)",
            instruction=ROOT_COORDINATOR_INSTRUCTION,
            sub_agents=[tp_agent, ta_agent],
            tools=[],  # Root agent doesn't need direct tools, sub-agents handle them
        )
        
        log = logging.getLogger("agent.travel_planner")
        log.info("Root agent created directly in travel_planner module")
        return root_agent
        
    except Exception as e:
        import logging
        log = logging.getLogger("agent.travel_planner")
        log.error(f"Failed to create root agent: {e}")
        return None

# Create the root agent directly
root_agent = _create_root_agent()

__all__ = ['travel_planner_agent', 'root_agent']
