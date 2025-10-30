"""
MCP module - FastAPI chatapp components
"""
from .mcp_tools import register_tools, move_agent
from .mcp_commands import handle_chat_message
from .mcp_reports import (
    generate_status_report,
    generate_detailed_report,
    list_agents,
    get_agent_info
)
from .mcp_menu import generate_startup_menu
from .mcp_streaming import (
    stream_postgresql,
    stream_qdrant,
    get_postgresql_data,
    get_qdrant_data
)

__all__ = [
    # Tools
    'register_tools',
    'move_agent',
    # Commands
    'handle_chat_message',
    # Reports
    'generate_status_report',
    'generate_detailed_report',
    'list_agents',
    'get_agent_info',
    # Menu
    'generate_startup_menu',
    # Streaming
    'stream_postgresql',
    'stream_qdrant',
    'get_postgresql_data',
    'get_qdrant_data',
]