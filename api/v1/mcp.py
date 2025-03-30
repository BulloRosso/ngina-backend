
from fastapi import APIRouter
from mcp import ClientSession
from mcp.client.sse import sse_client
import asyncio
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/mcp", tags=["mcp"])

class Tool(BaseModel):
    name: str
    description: str
    inputSchema: dict

@router.post("/tools", response_model=List[Tool])
async def get_tools():
    async with sse_client(url="http://127.0.0.1:5001/sse") as streams:
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
