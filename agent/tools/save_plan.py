import os
from typing import Any, List
import httpx

try:
    # Prefer official ADK function tool wrapper if available
    from google.adk.tools import function_tool as adk_function_tool
except Exception:  # pragma: no cover - optional at runtime
    adk_function_tool = None

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
    except Exception as e:  # pragma: no cover - defensive
        return {"status": "error", "message": str(e)}


def register_save_plan_tool() -> List:
    """Register the save plan function as an ADK tool if available.

    Returns a list of tool objects (possibly empty) to be passed to LlmAgent.
    """
    tools: List = []
    if adk_function_tool is None:
        # Fallback: return bare function so ADK can auto-wrap if supported
        tools.append(save_travel_plan)
        return tools
    try:
        tools.append(
            adk_function_tool(
                save_travel_plan,
                name="save_travel_plan",
                description="[ユーザー同意トークン必須] 現在のプラン(JSON.text, places, route_info)をサーバーへ保存する",
            )
        )
    except Exception:
        return []
    return tools
