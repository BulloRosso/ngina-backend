# api/v1/team.py
from fastapi import APIRouter, Depends
from uuid import UUID
from models.team import Team
from pydantic import BaseModel
from dependencies.auth import get_current_user
from services.team import TeamService, TeamConnectionsResponse

router = APIRouter(prefix="/team", tags=["team"])

# Request body model for adding agent
class AddAgentRequest(BaseModel):
    agentId: str

@router.get("", response_model=Team)
async def get_team(current_user: UUID = Depends(get_current_user)):
    """
    Get the team for the authenticated user.
    Creates a new team if none exists.
    """
    service = TeamService()
    return await service.get_or_create_team(current_user)

@router.post("/agents", response_model=Team)
async def add_agent_to_team(
    request: AddAgentRequest,
    current_user: UUID = Depends(get_current_user)
):
    """
    Add an agent to the authenticated user's team.
    """
    service = TeamService()
    return await service.add_agent(current_user, request.agentId)

@router.delete("/agents/{agent_id}", response_model=Team)
async def remove_agent_from_team(
    agent_id: str,
    current_user: UUID = Depends(get_current_user)
):
    """
    Remove an agent from the authenticated user's team.
    """
    service = TeamService()
    return await service.remove_agent(current_user, agent_id)

@router.get("/connections", response_model=TeamConnectionsResponse)
async def get_team_connections_endpoint(current_user: UUID = Depends(get_current_user)):
    """
    Get the team connections for the authenticated user.
    Returns a list of agents with their connection details.
    """
    service = TeamService()
    return await service.get_team_connections(current_user)