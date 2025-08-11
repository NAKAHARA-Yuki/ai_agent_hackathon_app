This folder contains optional tool wrappers for the travel_planner agent.

- maps_mcp.py: Registers retrieve_google_maps_platform_docs, a wrapper to call a Cloud Run MCP bridge.

The agent also uses the built-in ADK tool `google_search` from `google.adk.tools`, so no additional local implementation is required.
