# models/agent.py
from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel, UUID4, ConfigDict

class SchemaField(BaseModel):
    type: str
    description: Optional[str] = None

class I18nContent(BaseModel):
    de: Optional[str] = None
    en: Optional[str] = None

class AgentBase(BaseModel):
    title: Optional[I18nContent] = None
    description: Optional[I18nContent] = None
    input: Optional[Dict[str, SchemaField]] = None
    output: Optional[Dict[str, SchemaField]] = None
    credits_per_run: Optional[int] = 0
    workflow_id: Optional[str] = None
    stars: Optional[int] = 0
    image_url: Optional[str] = None
    max_execution_time_secs: Optional[int] = None
    agent_endpoint: Optional[str] = None

class AgentCreate(AgentBase):
    pass

class Agent(AgentBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    created_at: datetime