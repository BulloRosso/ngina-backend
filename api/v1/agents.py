# api/v1/agents.py
from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from models.agent import Agent
from pydantic import ValidationError, UUID4, BaseModel
import logging
from services.agents import AgentService, AgentTestRequest, SchemaGenerationRequest

logger = logging.getLogger(__name__) 

router = APIRouter(prefix="/agents", tags=["agents"])

@router.post("", response_model=Agent, summary="Create a new agent", description="Create a new agent with the provided configuration data", status_code=201, responses={201: {"description": "Agent created successfully"}, 422: {"description": "Validation error in request data"}, 500: {"description": "Server error during agent creation"}})
async def create_agent(agent_data: dict):
    service = AgentService()
    return await service.create_agent(agent_data)

@router.get("/{agent_id}", response_model=Agent, summary="Get agent by ID", description="Retrieve detailed information about a specific agent", responses={200: {"description": "Agent details retrieved successfully"}, 404: {"description": "Agent not found"}, 400: {"description": "Invalid UUID format"}, 500: {"description": "Server error"}})
async def get_agent(agent_id: str):
    try:
        service = AgentService()
        return await service.get_agent(agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=List[Agent], summary="List all agents", description="Retrieve a paginated list of all available agents", responses={200: {"description": "List of agents retrieved successfully"}, 500: {"description": "Server error"}})
async def list_agents(limit: Optional[int] = 100, offset: Optional[int] = 0):
    service = AgentService()
    return await service.list_agents(limit, offset)

@router.put("/{agent_id}", response_model=Agent, summary="Update an agent", description="Update an existing agent with new configuration data", responses={200: {"description": "Agent updated successfully"}, 404: {"description": "Agent not found"}, 422: {"description": "Validation error in request data"}, 500: {"description": "Server error"}})
async def update_agent(agent_id: UUID4, agent_data: dict):
    service = AgentService()
    return await service.update_agent(agent_id, agent_data)

@router.delete("/{agent_id}", summary="Delete an agent", description="Permanently remove an agent from the system", responses={200: {"description": "Agent deleted successfully"}, 404: {"description": "Agent not found"}, 500: {"description": "Server error"}})
async def delete_agent(agent_id: UUID4):
    service = AgentService()
    return await service.delete_agent(agent_id)

@router.post("/discover", response_model=Agent, summary="Discover an agent", description="Discover and register an agent from an external discovery URL", responses={200: {"description": "Agent discovered and registered successfully"}, 400: {"description": "Missing or invalid discovery URL"}, 422: {"description": "Agent returned invalid metadata"}, 500: {"description": "Server error or communication failure"}})
async def discover_agent(data: Dict[str, str]):
    if "agentDiscoveryUrl" not in data:
        raise HTTPException(status_code=400, detail="agentDiscoveryUrl is required")

    service = AgentService()
    return await service.discover_agent(data["agentDiscoveryUrl"])

@router.post("/{agent_id}/test", response_model=Dict[str, Any], summary="Test an agent", description="Run a test execution of an agent with the provided input data", responses={200: {"description": "Agent test executed successfully"}, 400: {"description": "Invalid UUID format or input data"}, 404: {"description": "Agent not found"}, 422: {"description": "Validation error in request data"}, 502: {"description": "Error communicating with the agent"}, 504: {"description": "Agent execution timed out"}, 500: {"description": "Server error"}})
async def test_agent(agent_id: str, test_data: AgentTestRequest):
    try:
        service = AgentService()
        return await service.test_agent(agent_id, test_data)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-json-schema", response_model=Dict[str, Any], summary="Generate JSON Schema", description="Generate a JSON schema from an example object", responses={200: {"description": "Schema generated successfully"}, 422: {"description": "Failed to generate schema from the provided data"}, 500: {"description": "Server error"}})
async def generate_json_schema(request: SchemaGenerationRequest):
    service = AgentService()
    return await service.generate_json_schema(request.data)