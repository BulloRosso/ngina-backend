# api/v1/team.py
from fastapi import APIRouter, HTTPException, Body
from typing import Optional
from models.team import Team, TeamCreate, TeamMember
from pydantic import BaseModel
from supabase import create_client
import logging
import os
from datetime import datetime

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
        self.owner_id = "a1234"  # Hardcoded as specified

    async def get_or_create_team(self) -> Team:
        try:
            # Try to get existing team
            result = self.supabase.table("teams")\
                .select("*")\
                .eq("owner_id", self.owner_id)\
                .execute()

            if result.data and len(result.data) > 0:
                return Team.model_validate(result.data[0])

            # Create new team if none exists
            new_team = TeamCreate()
            create_result = self.supabase.table("teams")\
                .insert(new_team.model_dump())\
                .execute()

            if not create_result.data:
                raise HTTPException(status_code=500, detail="Failed to create team")

            return Team.model_validate(create_result.data[0])

        except Exception as e:
            logging.error(f"Error in get_or_create_team: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get or create team: {str(e)}"
            )

    async def add_agent(self, agent_id: str) -> Team:
        try:
            # Get current team
            team = await self.get_or_create_team()

            # Check if agent is already in team
            current_members = team.agents.members if team.agents else []
            if any(member.agentId == agent_id for member in current_members):
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

            return Team.model_validate(result.data[0])

        except Exception as e:
            logging.error(f"Error adding agent to team: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to add agent to team: {str(e)}"
            )

    async def remove_agent(self, agent_id: str) -> Team:
        try:
            # Get current team
            team = await self.get_or_create_team()

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

            return Team.model_validate(result.data[0])

        except Exception as e:
            logging.error(f"Error removing agent from team: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to remove agent from team: {str(e)}"
            )

@router.get("", response_model=Team)
async def get_team():
    service = TeamService()
    return await service.get_or_create_team()

@router.post("/agents", response_model=Team)
async def add_agent_to_team(request: AddAgentRequest):
    service = TeamService()
    return await service.add_agent(request.agentId)

@router.delete("/agents/{agent_id}", response_model=Team)
async def remove_agent_from_team(agent_id: str):
    service = TeamService()
    return await service.remove_agent(agent_id)