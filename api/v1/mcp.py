
from fastapi import APIRouter
from mcp import ClientSession
from mcp.client.sse import sse_client
import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel

router = APIRouter(prefix="/mcp", tags=["mcp"])

default_mcp_server_url = "https://ed5ce8c5-8b5f-4bdc-b912-26e09e42b363-00-2ivmymeocpnno.janeway.replit.dev:8080/sse"


class Tool(BaseModel):
    name: str
    description: str
    inputSchema: dict

class ToolCallRequest(BaseModel):
    mcp_server_url: str = default_mcp_server_url
    toolName: str
    toolArgs: Dict[str, Any]
    
@router.post("/tools/sse", response_model=List[Tool])
async def get_tools(server_config: dict):
    """
    Lists the available tools on a server
    
    Accepts a JSON like this:
    {
      "mcp_server_url": "https://ed5ce8c5-8b5f-4bdc-b912-26e09e42b363-00-2ivmymeocpnno.janeway.replit.dev:8080/sse"
    }
    """
    mcp_server_url = server_config.get("mcp_server_url", default_mcp_server_url)

    async with sse_client(url=mcp_server_url) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = await session.list_tools()
            return [
                Tool(
                    name=tool.name,
                    description=tool.description,
                    inputSchema=tool.inputSchema
                )
                for tool in tools.tools
            ]

@router.post("/sse/tools/call")
async def call_tool(request: ToolCallRequest):
    """
    Call a specific MCP tool with the provided arguments.

    Args:
        request: Contains the MCP server URL, tool name, and tool arguments

    Returns:
        The JSON result from the tool execution
    """
    try:
        async with sse_client(url=request.mcp_server_url) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()

                # Validate that the requested tool exists
                tools_response = await session.list_tools()
                available_tools = [tool.name for tool in tools_response.tools]

                if request.toolName not in available_tools:
                    raise HTTPException(
                        status_code=404, 
                        detail=f"Tool '{request.toolName}' not found. Available tools: {available_tools}"
                    )

                # Call the tool with the provided arguments
                result = await session.call_tool(request.toolName, request.toolArgs)

                # Return the tool's response
                return {
                    "status": "success",
                    "toolName": request.toolName,
                    "result": result.content
                }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calling tool: {str(e)}"
        )