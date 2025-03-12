# models/scratchpad.py
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, UUID4, ConfigDict, Field,  field_validator

class ScratchpadFileMetadata(BaseModel):
    user_id: UUID4
    run_id: UUID4
    url: str
    created_at: datetime

class ScratchpadFile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    user_id: UUID4
    run_id: UUID4
    agent_id: str
    filename: str
    path: str
    metadata: ScratchpadFileMetadata
    created_at: datetime

    @field_validator('agent_id')
    @classmethod
    def validate_agent_id(cls, v):
        # Special case for the input agent ID
        if v == '00000000-0000-0000-0000-000000000001':
            return v
    
        # Otherwise, try to parse as UUID to validate format
        try:
            UUID(v, version=4)
        except ValueError:
            # If it's not a valid UUID, just let it pass if it's a string
            if not isinstance(v, str):
                raise ValueError("Agent ID must be a string")
    
        return v

class ScratchpadFiles(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    files: Dict[UUID4, List[ScratchpadFile]] = Field(default_factory=dict)

class ScratchpadFileResponse(BaseModel):
    metadata: ScratchpadFileMetadata
    url: str