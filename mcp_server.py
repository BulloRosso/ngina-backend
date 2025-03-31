# /mcp_server.py
from mcp.server.fastmcp import FastMCP, tools
import asyncio
import logging
import json
from typing import Any, Dict
import inspect
from jsonschema import validate

logger = logging.getLogger(__name__)

def register_tool_from_json(tool_json: Dict[str, Any], tool_manager: Any):
    """
    Create and register a tool from a JSON definition.

    Args:
        tool_json: Dictionary containing tool definition with 'title', 'description', and 'input'
        tool_manager: The ToolManager instance to register the tool with
        implementation_func: Optional function to use as implementation. If None, a placeholder will be created.

    Returns:
        The registered Tool instance
    """
    # Extract tool information from JSON
    tool_name = tool_json.get('title')
    tool_description = tool_json.get('description')
    tool_input_schema = tool_json.get('input')

    if not all([tool_name, tool_description, tool_input_schema]):
        raise ValueError("Tool JSON must contain 'title', 'description', and 'input' fields")

    # Extract parameter names from the input schema
    if 'properties' in tool_input_schema:
        param_names = list(tool_input_schema['properties'].keys())
    else:
        param_names = []

   
    # Create a dynamic signature based on the input schema parameters
    def implementation_func(**kwargs):
        # Validate input against schema
        validate(kwargs, tool_input_schema)
        # Placeholder implementation
        return f"Tool '{tool_name}' executed with parameters: {kwargs}"

    # Update function metadata to match expected parameters
    implementation_func.__name__ = tool_name
    implementation_func.__doc__ = tool_description

    # Use inspection to dynamically create a signature
    params = [inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY) for name in param_names]
    implementation_func.__signature__ = inspect.Signature(params)

    # Register the tool
    tool_manager.add_tool(implementation_func, name=tool_name, description=tool_description)

    return True

async def create_mcp_server(name="ngina-mpc-test-srv", port=5001, timeout=30):
    """
    Create and configure an MCP server instance.
    """
    mcp = FastMCP(name, port=port, timeout=timeout)
    logger.info(f"MCP server created with name: {name}, port: {port}, timeout: {timeout}")

    sample_tool_json = {
        "title": "Dynamic Object",
        "description": "A simple calculator that can perform basic arithmetic operations",
        "input": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["add", "subtract", "multiply", "divide"]},
                "a": {"type": "number"},
                "b": {"type": "number"}
            },
            "required": ["operation", "a", "b"]
        }
    }

    register_tool_from_json(sample_tool_json, mcp)

    tools = await mcp.list_tools()
    # Pretty print the tools as formatted JSON
    pretty_tools = json.dumps(tools, indent=4, sort_keys=True, default=str)
    logger.debug(f"Registered tools: \n{pretty_tools}")
    
    @mcp.tool()
    def add(a: int, b: int) -> int:
        """
        Add two integers and return sum.
        """
        return a + b 

    @mcp.tool() 
    def subtract(a: int, b: int) -> int:
        """
        Subtract two integers and return difference.
        """
        return a - b

    return mcp