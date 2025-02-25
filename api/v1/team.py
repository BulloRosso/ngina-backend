# api/v1/team.py
from fastapi import APIRouter, HTTPException, Body, Depends
from typing import  Optional, List, Dict, Any
from models.team import Team, TeamCreate, TeamMember
from pydantic import BaseModel, UUID4
from supabase import create_client
import logging
import os
from datetime import datetime
from dependencies.auth import get_current_user

router = APIRouter(prefix="/team", tags=["team"])

# Request body model for adding agent
class AddAgentRequest(BaseModel):
    agentId: str

class AgentConnection(BaseModel):
    agentId: str
    title: Optional[str] = None
    agent_endpoint: Optional[str] = None

class TeamConnectionsResponse(BaseModel):
    team: List[AgentConnection] = []
    
class TeamService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

    async def get_team_connections(self, owner_id: UUID4) -> TeamConnectionsResponse:
        try:
            # Get the user's team
            team = await self.get_or_create_team(owner_id)

            if not team.agents or not team.agents.members:
                # Return empty team if no agents
                return TeamConnectionsResponse(team=[])

            connections = []

            # Fetch details for each agent in the team
            for member in team.agents.members:
                try:
                    # Query the agents table to get basic agent details without input/output schemas
                    agent_result = self.supabase.table("agents")\
                        .select("id,title,agent_endpoint")\
                        .eq("id", member.agentId)\
                        .execute()

                    if agent_result.data and len(agent_result.data) > 0:
                        agent_data = agent_result.data[0]

                        # Extract English title from the JSON
                        title = None
                        if agent_data.get("title") and isinstance(agent_data["title"], dict):
                            title = agent_data["title"].get("en")

                        # Create connection entry WITHOUT input/output schemas
                        connection = AgentConnection(
                            agentId=member.agentId,
                            title=title,
                            agent_endpoint=agent_data.get("agent_endpoint")
                            # Do NOT include input/output schemas here
                        )
                        connections.append(connection)
                        logging.info(f"Added agent connection for {member.agentId} with title: {title}")
                    else:
                        # Include the agent ID even if details aren't found
                        connections.append(AgentConnection(agentId=member.agentId))
                        logging.warning(f"Agent details not found for ID: {member.agentId}")

                except Exception as e:
                    logging.error(f"Error fetching agent {member.agentId}: {str(e)}")
                    # Still include the agent ID in case of error
                    connections.append(AgentConnection(agentId=member.agentId))

            return TeamConnectionsResponse(team=connections)

        except Exception as e:
            logging.error(f"Error in get_team_connections: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get team connections: {str(e)}"
            )
          
    async def get_or_create_team(self, owner_id: UUID4) -> Team:
        try:
            # Convert UUID to string for the teams table query
            owner_id_str = str(owner_id)
            logging.info(f"Looking up team for owner: {owner_id_str}")

            # Try to get existing team
            result = self.supabase.table("teams")\
                .select("*")\
                .eq("owner_id", owner_id_str)\
                .execute()

            if result.data and len(result.data) > 0:
                logging.info(f"Found existing team: {result.data[0]}")
                return Team.model_validate(result.data[0])

            # Create new team if none exists
            logging.info("No team found, creating new team")
            new_team = TeamCreate(owner_id=owner_id_str)
            create_result = self.supabase.table("teams")\
                .insert(new_team.model_dump())\
                .execute()

            if not create_result.data:
                raise HTTPException(status_code=500, detail="Failed to create team")

            logging.info(f"Created new team: {create_result.data[0]}")
            return Team.model_validate(create_result.data[0])

        except Exception as e:
            logging.error(f"Error in get_or_create_team: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get or create team: {str(e)}"
            )

    async def add_agent(self, owner_id: UUID4, agent_id: str) -> Team:
        try:
            logging.info(f"Adding agent {agent_id} to team")
            # Get current team
            team = await self.get_or_create_team(owner_id)

            # Check if agent is already in team
            current_members = team.agents.members if team.agents else []
            if any(member.agentId == agent_id for member in current_members):
                logging.info(f"Agent {agent_id} already in team")
                return team

            # Add new agent
            new_members = current_members + [TeamMember(agentId=agent_id)]
            update_data = {
                "agents": {
                    "members": [member.model_dump() for member in new_members]
                }
            }

            result = self.supabase.table("teams")\
                .update(update_data)\
                .eq("id", str(team.id))\
                .execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="Failed to update team")

            logging.info(f"Successfully added agent {agent_id} to team")
            return Team.model_validate(result.data[0])

        except Exception as e:
            logging.error(f"Error adding agent to team: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to add agent to team: {str(e)}"
            )

    async def remove_agent(self, owner_id: UUID4, agent_id: str) -> Team:
        try:
            logging.info(f"Removing agent {agent_id} from team")
            # Get current team
            team = await self.get_or_create_team(owner_id)

            # Remove agent from members
            current_members = team.agents.members if team.agents else []
            new_members = [m for m in current_members if m.agentId != agent_id]

            update_data = {
                "agents": {
                    "members": [member.model_dump() for member in new_members]
                }
            }

            result = self.supabase.table("teams")\
                .update(update_data)\
                .eq("id", str(team.id))\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Team not found")

            logging.info(f"Successfully removed agent {agent_id} from team")
            return Team.model_validate(result.data[0])

        except Exception as e:
            logging.error(f"Error removing agent from team: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to remove agent from team: {str(e)}"
            )

@router.get("", response_model=Team)
async def get_team(current_user: UUID4 = Depends(get_current_user)):
    """
    Get the team for the authenticated user.
    Creates a new team if none exists.
    """
    service = TeamService()
    return await service.get_or_create_team(current_user)

@router.post("/agents", response_model=Team)
async def add_agent_to_team(
    request: AddAgentRequest,
    current_user: UUID4 = Depends(get_current_user)
):
    """
    Add an agent to the authenticated user's team.
    """
    service = TeamService()
    return await service.add_agent(current_user, request.agentId)

@router.delete("/agents/{agent_id}", response_model=Team)
async def remove_agent_from_team(
    agent_id: str,
    current_user: UUID4 = Depends(get_current_user)
):
    """
    Remove an agent from the authenticated user's team.
    """
    service = TeamService()
    return await service.remove_agent(current_user, agent_id)

@router.get("/connections", response_model=TeamConnectionsResponse)
async def get_team_connections_endpoint(current_user: UUID4 = Depends(get_current_user)):
    """
    Get the team connections for the authenticated user.
    Returns a list of agents with their connection details.
    """
    service = TeamService()
    return await service.get_team_connections(current_user)