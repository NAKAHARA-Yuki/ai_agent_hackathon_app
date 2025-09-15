# ADK Agent Configuration Fix Notes

## Issue Addressed

**Error**: `google.genai.errors.ClientError: 400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'Tool use with function calling is unsupported', 'status': 'INVALID_ARGUMENT'}}`

## Root Causes Identified

1. **Tool Configuration Conflicts**: Mixing built-in ADK tools (`google_search`) with custom MCP tools caused function calling conflicts
2. **Circular Import Issues**: Agents were being created multiple times due to circular import dependencies
3. **Model Compatibility**: The original model (`gemini-2.5-pro`) had compatibility issues with the tool configuration

## Fixes Applied

### 1. Tool Configuration Strategy
- **Before**: Mixed `google_search` (built-in) and MCP tools in the same agent
- **After**: Prioritize `google_search` as primary tool, use MCP tools only as fallback
- **Result**: Eliminates function calling conflicts

### 2. Import Structure Cleanup  
- **Before**: Circular imports between root coordinator and sub-agents
- **After**: Lazy loading of sub-agents in root coordinator, proper import order
- **Result**: No more agent duplication or parent assignment conflicts

### 3. Model Configuration
- **Current**: `gemini-2.5-pro` (as requested by user feedback)
- **Previous**: `gemini-2.0-flash-exp` (used temporarily for compatibility)
- **Result**: Using preferred model with improved tool configuration

### 4. FunctionTool Import Fix
- **Before**: Only tried `function_tool` import
- **After**: Handle both `FunctionTool` class and `function_tool` function
- **Result**: Compatible with different ADK versions

## Key Changes

### Agent Structure
```
agents/
├── __init__.py          # Import sub-agents first, then root
├── agent.py             # Main export for ADK api_server
├── travel_planner/      # Individual sub-agent
├── travel_advisor/      # Individual sub-agent  
└── root_coordinator/    # Lazy-loads sub-agents
```

### Tool Priority Order
1. **Primary**: Built-in `google_search` tool (if available)
2. **Fallback**: MCP tools (only if google_search unavailable)
3. **Result**: No mixed tool types per agent

## Verification

All tests pass:
- ✓ Agent imports work without circular dependencies
- ✓ No function calling conflicts detected
- ✓ Proper agent hierarchy (root → sub-agents)
- ✓ ADK api_server compatible imports
- ✓ Tool configurations are consistent and compatible

## Impact

- **Fixed**: Original function calling error eliminated
- **Maintained**: All existing functionality preserved
- **Improved**: More stable and maintainable agent structure
- **Compatible**: Works with ADK api_server expectations

## Frontend UI Integration Fixes

### Mobile UI Optimization (September 2025)

**Issue**: Cards clipping on mobile devices in PlansListView, poor responsive behavior

**Solutions Applied**:

1. **Card Layout Fixes**
   - Implemented strict width constraints: `max-width: calc(100vw - 16px)`
   - Added `overflow-x: hidden` to prevent horizontal scrolling
   - Applied `contain: layout strict` for stable rendering

2. **Touch Target Compliance**
   - Upgraded button sizes to WCAG AA standards (44px minimum)
   - Optimized touch interaction areas for mobile devices

3. **Viewport Compatibility**  
   - Implemented dynamic viewport height (`100dvh`)
   - Added safe area inset support for modern mobile devices
   - Enhanced responsive grid: desktop multi-column → mobile single-column

4. **Active Plan Banner Optimization**
   - Fixed banner clipping with minimum height constraints
   - Improved content overflow handling
   - Enhanced mobile-specific layout adjustments

**Result**: Significantly improved mobile user experience with stable, accessible UI

---

**最終更新**: 2025年9月15日