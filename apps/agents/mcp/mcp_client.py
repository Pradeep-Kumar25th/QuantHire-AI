"""
MCP Client for Agent Integration
Allows LangGraph/CrewAI agents to call MCP servers
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP Client for agents to call MCP servers.
    
    Usage:
        client = MCPClient()
        result = await client.call_tool(
            "calendar-server",
            "get_calendar_availability",
            {"user_email": "user@example.com", ...}
        )
    """
    
    def __init__(self):
        """Initialize MCP client."""
        self.servers: Dict[str, StdioServerParameters] = {}
        self._sessions: Dict[str, Any] = {}
        self._initialize_servers()
    
    def _initialize_servers(self):
        """Initialize known MCP servers."""
        import os
        base_path = os.path.join(os.path.dirname(__file__), "../../")
        
        # Calendar MCP Server
        self.servers["calendar-server"] = StdioServerParameters(
            command="python",
            args=[os.path.join(base_path, "mcp_servers/calendar/calendar_mcp_server.py")]
        )
        
        # Add more servers as needed
        # self.servers["database-server"] = StdioServerParameters(...)
        # self.servers["notification-server"] = StdioServerParameters(...)
    
    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call an MCP tool.
        
        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool result as dictionary
        """
        if server_name not in self.servers:
            raise ValueError(f"Unknown MCP server: {server_name}")
        
        server_params = self.servers[server_name]
        
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize connection
                    await session.initialize()
                    
                    # List available tools
                    tools = await session.list_tools()
                    
                    # Find the tool
                    tool = next(
                        (t for t in tools.tools if t.name == tool_name),
                        None
                    )
                    
                    if not tool:
                        available_tools = [t.name for t in tools.tools]
                        raise ValueError(
                            f"Tool '{tool_name}' not found. "
                            f"Available tools: {available_tools}"
                        )
                    
                    # Call the tool
                    logger.info(f"Calling MCP tool: {server_name}/{tool_name}")
                    result = await session.call_tool(tool_name, arguments)
                    
                    # Parse result
                    if result.content:
                        if isinstance(result.content[0].text, str):
                            try:
                                return json.loads(result.content[0].text)
                            except json.JSONDecodeError:
                                return {"result": result.content[0].text}
                        return result.content[0].text
                    
                    return {}
        
        except Exception as e:
            logger.error(f"Error calling MCP tool {server_name}/{tool_name}: {e}")
            raise
    
    async def list_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """
        List available tools from an MCP server.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            List of tool information
        """
        if server_name not in self.servers:
            raise ValueError(f"Unknown MCP server: {server_name}")
        
        server_params = self.servers[server_name]
        
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    
                    return [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.inputSchema,
                        }
                        for tool in tools.tools
                    ]
        
        except Exception as e:
            logger.error(f"Error listing tools from {server_name}: {e}")
            raise


# Global MCP client instance
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get global MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client
