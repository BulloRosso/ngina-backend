# models/agent.py
from datetime import datetime
from typing import Optional, Dict, Any
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
    input: Optional[Any] = None
    output: Optional[Any] = None
    input_example: Optional[Any] = None
    output_example: Optional[Any] = None
    credits_per_run: Optional[int] = 0
    workflow_id: Optional[str] = None
    workflow_webhook_url: Optional[str] = None
    stars: Optional[int] = 0
    content_extraction_file_extensions: Optional[str] = None
    authentication: Optional[str] = None
    icon_svg: Optional[str] = None
    wrapped_url: Optional[str] = None
    task_prompt: Optional[str] = None
    max_execution_time_secs: Optional[int] = None
    agent_endpoint: Optional[str] = None
    type: Optional[str] = "atom"
    output_type: Optional[str] = "content-creation"
    configuration: Optional[Any] = None

class AgentCreate(AgentBase):
    pass

class Agent(AgentBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    created_at: datetime