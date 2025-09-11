# Main agent entry point for ADK api_server
# This file exports the root coordinator agent as the main 'agent' symbol

try:
    from .root_coordinator import root_agent
    # ADK api_server expects symbol `agent`
    agent = root_agent
except ImportError as e:
    import logging
    logging.error(f"Failed to import root coordinator agent: {e}")
    raise