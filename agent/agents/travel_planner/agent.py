import os
from google.adk.agents import LlmAgent
from tools.maps_mcp import register_maps_mcp_tool

# Bridge GEMINI_API_KEY -> GOOGLE_API_KEY for google-genai used by ADK
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
	os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
	os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

DEFAULT_INSTRUCTION = (
	"あなたは日本国内旅行のコンシェルジュです。常に丁寧で、簡潔な日本語で応答してください。\n\n"
	"入力メッセージには、次の2つのセクションが含まれる場合があります。\n"
	"1) [ユーザー情報] ← JSON（例: persona.title/description/traitScores, user.profile.display_name/age/gender/hobbies/location/budget/notes など）\n"
	"2) [ユーザーからの依頼] ← ユーザーの要望テキスト\n\n"
	"方針:\n"
	"- [ユーザー情報] があれば必ず個人化（年齢・興味・予算・出発地・季節など）に活用する。\n"
	"- 安全性・移動時間・費用感に配慮し、現実的な候補を示す。\n"
	"- 返信は会話に適した短い段落で。最初に結論、その後に補足。\n"
	"- 必要に応じて `retrieve_google_maps_platform_docs` ツールで最新ガイドラインを参照する。\n\n"
	"出力形式:\n"
	"- 既定はチャット応答のみ（短い日本語の文章）。\n"
	"- 地図表示のために候補地を添える場合は、応答末尾で JSON を提示（例: {\"places\":[{\"name\":\"箱根温泉\",\"lat\":null,\"lng\":null,\"note\":\"美術館と温泉\"}]}）。\n"
	"  緯度経度が不明な場合は null を入れてもよい（サーバ側でジオコーディングする）。\n"
)

INSTRUCTION = os.getenv("AGENT_INSTRUCTION_OVERRIDE") or DEFAULT_INSTRUCTION

tools = register_maps_mcp_tool()

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
