# models/team.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, UUID4, ConfigDict

class TeamMember(BaseModel):
    agentId: str

class TeamAgents(BaseModel):
    members: List[TeamMember] = []

class TeamBase(BaseModel):
    owner_id: str = "a1234"  # Hardcoded as specified
    agents: Optional[TeamAgents] = TeamAgents()

class TeamCreate(TeamBase):
    pass

class Team(TeamBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    created_at: datetime