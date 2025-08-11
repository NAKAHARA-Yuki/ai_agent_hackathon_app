import os
import json
import httpx
import os
from google.adk.agents import LlmAgent
try:
    # Prefer official ADK function tool wrapper if available
    from google.adk.tools import function_tool as adk_function_tool
except Exception:
    adk_function_tool = None

# Bridge GEMINI_API_KEY -> GOOGLE_API_KEY for google-genai used by ADK
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

DEFAULT_INSTRUCTION = (
    "あなたは日本国内旅行のプランナーです。次のJSON入力（ペルソナ/プロファイル/制約）を読み、"
    "3つの旅行プランを日本語で提案してください。出力は必ず次の形式のみで返してください。\n\n"
    "入力例:\n"
    "{\n  \"persona\":{\"title\":\"◯◯タイプ\",\"description\":\"...\",\"traitScores\":{}},\n"
    "  \"profile\":{\"display_name\":\"...\"},\n  \"constraints\":{\"season\":\"春\"}\n}\n\n"
    "出力(JSONのみ):\n"
    "{\n  \"plans\": [\n    {\"title\": \"...\", \"description\": \"...\"},\n"
    "    {\"title\": \"...\", \"description\": \"...\"},\n"
    "    {\"title\": \"...\", \"description\": \"...\"}\n  ]\n}\n\n"
    "制約:\n- 国内旅行に限定\n- 地域はなるべく分散（北/東/西など）\n- 日本語で簡潔に\n\n"
    "注記: 必要に応じて `retrieve_google_maps_platform_docs` ツールを用い、最新のGoogle Maps Platform公式ガイドに準拠した提案やコード方針を参考にしてください。"
)

INSTRUCTION = os.getenv("AGENT_INSTRUCTION_OVERRIDE") or DEFAULT_INSTRUCTION

# Root agent exposed to ADK Web/UI
MAPS_MCP_ENDPOINT_URL = os.getenv("MAPS_MCP_ENDPOINT_URL")  # e.g., https://maps-mcp-service-xxxx.a.run.app/tools/retrieve-google-maps-platform-docs
MAPS_MCP_AUDIENCE = os.getenv("MAPS_MCP_AUDIENCE")  # e.g., https://maps-mcp-service-xxxx.a.run.app

async def retrieve_google_maps_platform_docs(query: str) -> str:
    """Retrieve relevant Google Maps Platform docs/snippets via MCP bridge.
    Requires MAPS_MCP_ENDPOINT_URL to be configured to an HTTP endpoint that accepts {"query": str} and returns text or {text}.
    """
    if not MAPS_MCP_ENDPOINT_URL:
        return "[maps-mcp] 未設定: MAPS_MCP_ENDPOINT_URL を設定してください。"
    try:
        headers = {"Content-Type": "application/json"}
        # If audience is provided, fetch an identity token from metadata server (Cloud Run) and include it
        token = None
        if MAPS_MCP_AUDIENCE and os.getenv('K_SERVICE'):
            try:
                md_url = (
                    f"http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?"
                    f"audience={MAPS_MCP_AUDIENCE}&format=full"
                )
                async with httpx.AsyncClient(timeout=5.0) as md:
                    md_resp = await md.get(md_url, headers={"Metadata-Flavor": "Google"})
                    if md_resp.status_code == 200:
                        token = md_resp.text.strip()
            except Exception:
                token = None
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(MAPS_MCP_ENDPOINT_URL, headers=headers, json={"query": query})
            r.raise_for_status()
            ct = r.headers.get("content-type", "")
            if "application/json" in ct:
                data = r.json()
                # Accept common shapes
                if isinstance(data, dict):
                    return data.get("text") or data.get("content") or json.dumps(data, ensure_ascii=False)
                return json.dumps(data, ensure_ascii=False)
            return r.text
    except Exception as e:
        return f"[maps-mcp] 呼び出しに失敗しました: {e}"

# Wrap as ADK tool when possible
tools = []
if adk_function_tool is not None:
    try:
        maps_docs_tool = adk_function_tool(retrieve_google_maps_platform_docs, name="retrieve_google_maps_platform_docs", description="Google Maps Platformの最新ドキュメント/コードを検索し要約を返す")
        tools.append(maps_docs_tool)
    except Exception:
        pass

root_agent = LlmAgent(
    name="travel_planner",
    model=MODEL,
    description="Generate domestic travel plans in Japanese from persona/profile/constraints",
    instruction=INSTRUCTION,
    tools=tools,
)
