# Travel Planner Sub-Agent and Root Agent Exposure
from .agent import travel_planner_agent

# Import the root_agent from root_coordinator to expose it here
# This is required by ADK agent loader when looking for 'travel_planner' agent
try:
    from ..root_coordinator.agent import root_agent
    __all__ = ['travel_planner_agent', 'root_agent']
except ImportError as e:
    # If root_coordinator is not available, we need to create the root_agent here
    # Import the root_coordinator agent definition and create it
    import logging
    log = logging.getLogger("agent.travel_planner.init")
    log.warning(f"Failed to import root_agent from root_coordinator: {e}")
    
    try:
        # Import and create the root agent directly
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        
        from root_coordinator.agent import root_agent
        __all__ = ['travel_planner_agent', 'root_agent']
        log.info("Successfully imported root_agent via fallback path")
    except Exception as e2:
        log.error(f"Fallback import also failed: {e2}")
        root_agent = None
        __all__ = ['travel_planner_agent']
