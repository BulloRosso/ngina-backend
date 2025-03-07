# models/operation.py
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, UUID4, ConfigDict

class AgentStatus(BaseModel):
    title: str  # Just the English title
    lastRun: Optional[Dict[str, Any]] = None

class TeamStatus(BaseModel):
    agents: List[AgentStatus]

class OperationBase(BaseModel):
    agent_id: Optional[UUID4] = None
    results: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    prompt: Optional[str] = None
    sum_credits: Optional[int] = 0
    workflow_id: Optional[str] = None
    finished_at: Optional[datetime] = None
    user_id: Optional[UUID4] = None

class OperationCreate(OperationBase):
    pass

class Operation(OperationBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    created_at: datetime