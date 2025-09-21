"""General Chat Agent for location-based queries and general travel assistance"""
import os
import logging
from adk import LlmAgent
from adk.tools import GoogleSearchTool

# Minimal logging setup
_LEVEL = (os.getenv("LOG_LEVEL") or "INFO").upper()
logging.basicConfig(level=getattr(logging, _LEVEL, logging.INFO), format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
log = logging.getLogger("agent.general_chat")

# Model configuration
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro") 
log.info(f"General Chat Agent model: {MODEL}")

GENERAL_CHAT_INSTRUCTION = (
    "あなたは一般的な旅行相談と位置情報に基づく案内を行う旅行アシスタントです。\n\n"
    "主な機能:\n"
    "1) 現在位置周辺の観光スポット、レストラン、施設の案内\n"
    "2) 旅行に関する一般的な質問への回答\n"
    "3) 交通手段や移動方法の提案\n"
    "4) リアルタイムな地域情報の提供\n\n"
    "位置情報が提供された場合:\n"
    "- Google検索を使用して現在地周辺の最新情報を取得\n"
    "- 具体的な場所名、住所、営業時間、口コミ情報を含める\n"
    "- 移動手段（徒歩、電車、バス等）と所要時間を併記\n\n"
    "回答は日本語で、親しみやすく実用的な内容にしてください。\n"
    "不明な点は素直に「わからない」と答え、調べ方を提案してください。"
)

# Initialize tools - using Google Search for real-time location info
tools = []

try:
    google_search_tool = GoogleSearchTool()
    tools.append(google_search_tool)
    log.info("Google Search tool initialized successfully")
except Exception as e:
    log.warning(f"Failed to initialize Google Search tool: {e}")

# Create the general chat agent
general_chat_agent = LlmAgent(
    name="general_chat",
    model=MODEL,
    description="General travel chat agent with location-based assistance using Google Maps and search",
    instruction=GENERAL_CHAT_INSTRUCTION,
    tools=tools,
)

log.info(f"General Chat Agent initialized with {len(tools)} tool(s)")