from mcp import ClientSession
from mcp.client.sse import sse_client

async def run():
  async with sse_client(url="https://ed5ce8c5-8b5f-4bdc-b912-26e09e42b363-00-2ivmymeocpnno.janeway.replit.dev:8080/sse") as streams:
    async with ClientSession(*streams) as session:
      await session.initialize()

      # List available tools
      tools = await session.list_tools()
      print(tools)

      # call a tool
      result = await session.call_tool("add", arguments = {"a": 1, "b": 2})
      print(result)

if __name__ == "__main__":
  import asyncio

  asyncio.run(run())