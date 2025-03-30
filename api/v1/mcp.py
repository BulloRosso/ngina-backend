
from fastapi import APIRouter
from mcp import ClientSession
from mcp.client.sse import sse_client
import asyncio
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/mcp", tags=["mcp"])

external_mcp_server_url = "https://ed5ce8c5-8b5f-4bdc-b912-26e09e42b363-00-2ivmymeocpnno.janeway.replit.dev:8080/sse"


class Tool(BaseModel):
    name: str
    description: str
    inputSchema: dict

@router.post("/tools/sse", response_model=List[Tool])
async def get_tools(server_config: dict):
    """
    Lists the available tools on a server
    
    Accepts a JSON like this:
    {
      "mcp_server_url": "https://ed5ce8c5-8b5f-4bdc-b912-26e09e42b363-00-2ivmymeocpnno.janeway.replit.dev:8080/sse"
    }
    """
    mcp_server_url = server_config.get("mcp_server_url", external_mcp_server_url)

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
