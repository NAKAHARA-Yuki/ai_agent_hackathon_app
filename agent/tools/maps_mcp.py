import json
import os
from typing import List

import httpx

try:
    # Prefer official ADK function tool wrapper if available
    from google.adk.tools import FunctionTool
    adk_function_tool = FunctionTool
except ImportError:
    try:
        # Fallback to function_tool if FunctionTool is not available
        from google.adk.tools import function_tool as adk_function_tool
    except ImportError:  # pragma: no cover - optional at runtime
        adk_function_tool = None


MAPS_MCP_ENDPOINT_URL = os.getenv("MAPS_MCP_ENDPOINT_URL")  # e.g., https://maps-mcp-xxxxx.a.run.app/tools/retrieve-google-maps-platform-docs
MAPS_MCP_AUDIENCE = os.getenv("MAPS_MCP_AUDIENCE")  # e.g., https://maps-mcp-xxxxx.a.run.app


async def retrieve_google_maps_platform_docs(query: str) -> str:
    """Call the Maps MCP HTTP bridge to retrieve relevant docs/snippets.

    Returns a plain text summary or JSON as a string on success, otherwise an
    error string beginning with [maps-mcp].
    """
    if not MAPS_MCP_ENDPOINT_URL:
        return "[maps-mcp] 未設定: MAPS_MCP_ENDPOINT_URL を設定してください。"

    headers = {"Content-Type": "application/json"}

    # When running on Cloud Run and an audience is set, fetch an ID token
    token = None
    if MAPS_MCP_AUDIENCE and os.getenv("K_SERVICE"):
        try:
            md_url = (
                "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/"
                "default/identity?audience="
                + MAPS_MCP_AUDIENCE
                + "&format=full"
            )
            async with httpx.AsyncClient(timeout=5.0) as md:
                md_resp = await md.get(md_url, headers={"Metadata-Flavor": "Google"})
                if md_resp.status_code == 200:
                    token = md_resp.text.strip()
        except Exception:
            token = None

    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(MAPS_MCP_ENDPOINT_URL, headers=headers, json={"query": query})
            r.raise_for_status()
            ct = r.headers.get("content-type", "")
            if "application/json" in ct:
                data = r.json()
                if isinstance(data, dict):
                    return data.get("text") or data.get("content") or json.dumps(data, ensure_ascii=False)
                return json.dumps(data, ensure_ascii=False)
            return r.text
    except Exception as e:  # pragma: no cover - defensive
        return f"[maps-mcp] 呼び出しに失敗しました: {e}"


def register_maps_mcp_tool() -> List:
    """Register the MCP retrieval function as an ADK tool if available.

    Returns a list of tool objects (possibly empty) to be passed to LlmAgent.
    """
    tools: List = []
    if adk_function_tool is None:
        return tools
    try:
        if hasattr(adk_function_tool, '__call__'):
            # If it's a function (function_tool)
            tools.append(
                adk_function_tool(
                    retrieve_google_maps_platform_docs,
                    name="retrieve_google_maps_platform_docs",
                    description="Google Maps Platformの最新ドキュメント/コードを検索し要約を返す",
                )
            )
        else:
            # If it's a class (FunctionTool)
            tools.append(
                adk_function_tool(retrieve_google_maps_platform_docs)
            )
    except Exception:
        # Fail closed; simply don't register the tool
        return []
    return tools
