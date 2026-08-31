"""
LangChain Tool Wrappers for MCP Servers
Allows LangGraph/CrewAI agents to use MCP tools as LangChain tools
"""

import json
import asyncio
from typing import Optional, Type, List
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from apps.agents.mcp.mcp_client import get_mcp_client


class MCPToolInput(BaseModel):
    """Input schema for MCP tool."""
    arguments: dict = Field(description="Tool arguments as dictionary")


class MCPTool(BaseTool):
    """
    LangChain tool wrapper for MCP tools.
    
    Usage:
        tool = MCPTool(
            server_name="calendar-server",
            tool_name="get_calendar_availability",
            description="Get calendar availability for a user"
        )
        
        # Use in agent
        agent = create_react_agent(llm, tools=[tool])
    """
    
    server_name: str
    tool_name: str
    mcp_client = None
    
    def __init__(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        **kwargs
    ):
        """Initialize MCP tool."""
        super().__init__(
            name=f"{server_name}_{tool_name}",
            description=description,
            args_schema=MCPToolInput,
            **kwargs
        )
        self.server_name = server_name
        self.tool_name = tool_name
        self.mcp_client = get_mcp_client()
    
    def _run(self, arguments: dict) -> str:
        """Synchronous execution (runs async in event loop)."""
        return asyncio.run(self._arun(arguments))
    
    async def _arun(self, arguments: dict) -> str:
        """Asynchronous execution."""
        try:
            result = await self.mcp_client.call_tool(
                server_name=self.server_name,
                tool_name=self.tool_name,
                arguments=arguments
            )
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error: {str(e)}"


# Pre-configured MCP tools for common use cases

def create_calendar_tools() -> List[MCPTool]:
    """Create all calendar MCP tools as LangChain tools."""
    return [
        MCPTool(
            server_name="calendar-server",
            tool_name="get_calendar_availability",
            description="Get calendar availability for a user. Returns available time slots."
        ),
        MCPTool(
            server_name="calendar-server",
            tool_name="find_meeting_times",
            description="Find mutually available meeting times for multiple attendees."
        ),
        MCPTool(
            server_name="calendar-server",
            tool_name="create_calendar_event",
            description="Create a calendar event/meeting and send invites to attendees."
        ),
        MCPTool(
            server_name="calendar-server",
            tool_name="update_calendar_event",
            description="Update an existing calendar event."
        ),
        MCPTool(
            server_name="calendar-server",
            tool_name="cancel_calendar_event",
            description="Cancel a calendar event."
        ),
    ]


