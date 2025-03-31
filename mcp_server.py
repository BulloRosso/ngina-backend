# /mcp_server.py
from mcp.server.fastmcp import FastMCP, tools
import asyncio
import logging
import json
from typing import Any, Dict
import inspect
import os
from jsonschema import validate
from supabase import create_client
from services.agents import AgentService

logger = logging.getLogger(__name__)

async def register_agents_as_tools(mcp):
    """
    Registers all agents tagged with "compliance:MCP" as tools in the MCP server.

    Args:
        mcp: The FastMCP instance to register the tools with

    Returns:
        int: Number of agents registered as tools
    """
    logger.info("Starting to register agents tagged with compliance:MCP as tools")

    # Create Supabase client
    supabase = create_client(
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_key=os.getenv("SUPABASE_KEY")
    )

    # Initialize the agent service
    agent_service = AgentService()

    try:
        # Step 1: Get all agents with the tag "compliance:MCP"
        result = supabase.table("agent_tags") \
            .select("agent_id") \
            .ilike("tags", "%compliance:MCP%") \
            .execute()

        if not result.data:
            logger.info("No agents found with tag compliance:MCP")
            return 0

        # Extract agent IDs
        agent_ids = [item["agent_id"] for item in result.data]
        logger.info(f"Found {len(agent_ids)} agents with tag compliance:MCP: {agent_ids}")

        # Track registered tools count
        registered_count = 0

        # Step 2: For each tagged agent, fetch details and register as a tool
        for agent_id in agent_ids:
            try:
                # Get agent details
                agent = await agent_service.get_agent(agent_id)

                # Skip agents without proper schema
                if not agent.input or not agent.title:
                    logger.warning(f"Agent {agent_id} missing required fields (input schema or title)")
                    continue

                # Create tool name from title - replace spaces with underscores
                tool_name = agent.title.en.replace(" ", "_") if agent.title.en else f"agent_{agent_id}"

                # Get description
                description = agent.description.en if agent.description and agent.description.en else "No description provided"

                # Extract parameter names from the input schema
                param_names = []
                if "properties" in agent.input:
                    param_names = list(agent.input["properties"].keys())

                # Create a dynamic implementation function
                def create_implementation_func(agent_id, tool_name, input_schema):
                    def implementation_func(**kwargs):
                        # Validate input against schema
                        validate(kwargs, input_schema)

                        # Simple placeholder implementation
                        return f"Tool '{tool_name}' executed with parameters: {kwargs}"

                    # Update function metadata
                    implementation_func.__name__ = tool_name
                    implementation_func.__doc__ = description

                    # Create dynamic signature
                    params = [inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY) for name in param_names]
                    implementation_func.__signature__ = inspect.Signature(params)

                    return implementation_func

                # Create and register the tool
                tool_func = create_implementation_func(agent_id, tool_name, agent.input)
                mcp.add_tool(tool_func, name=tool_name, description=description)

                logger.info(f"Successfully registered agent {agent_id} as tool '{tool_name}'")
                registered_count += 1

            except Exception as e:
                logger.error(f"Error registering agent {agent_id} as tool: {str(e)}")
                continue

        logger.info(f"Successfully registered {registered_count} agents as tools")
        return registered_count

    except Exception as e:
        logger.error(f"Error registering agents as tools: {str(e)}")
        return 0

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

    #sample_tool_json = {
    #    "title": "Dynamic Object",
    #    "description": "A simple calculator that can perform basic arithmetic operations",
    #    "input": {
    #        "type": "object",
    #        "properties": {
    #            "operation": {"type": "string", "enum": ["add", "subtract", "multiply", "divide"]},
    #            "a": {"type": "number"},
    #            "b": {"type": "number"}
    #        },
    #        "required": ["operation", "a", "b"]
    #    }
    #}

    # register_tool_from_json(sample_tool_json, mcp)
    await register_agents_as_tools(mcp)

    tools = await mcp.list_tools()
    # Pretty print the tools as formatted JSON
    pretty_tools = json.dumps(tools, indent=4, sort_keys=True, default=str)
    logger.debug(f"Registered tools: \n{pretty_tools}")
    
    # @mcp.tool()
    #def add(a: int, b: int) -> int:
    #    """
    #    Add two integers and return sum.
    #    """
    #    return a + b 

    #@mcp.tool() 
    #def subtract(a: int, b: int) -> int:
    #    """
    #    Subtract two integers and return difference.
    #    """
    #    return a - b

    return mcp