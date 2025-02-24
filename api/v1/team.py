# api/v1/team.py
from fastapi import APIRouter, HTTPException, Body, Depends
from typing import Optional
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

class TeamService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
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