# models/context.py
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, UUID4, RootModel

class AgentContext(BaseModel):
    """Model representing the context of a single agent."""
    prompt: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    input: Optional[Any] = None
    input_example: Optional[Any] = None
    output: Optional[Any] = None
    output_example: Optional[Any] = None

class BuildContextRequest(BaseModel):
    """Request model for building context from an agent chain."""
    agentChain: List[str]

class ContextResponse(RootModel):
    """Response model containing agent contexts indexed by agent ID."""
    root: Dict[str, AgentContext]

class PromptToJsonRequest(BaseModel):
    """Request model for prompt to JSON conversion."""
    prompt: str
    one_shot: bool = True