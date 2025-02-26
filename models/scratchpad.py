# models/scratchpad.py
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, UUID4, ConfigDict, Field

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
    agent_id: UUID4
    filename: str
    path: str
    metadata: ScratchpadFileMetadata
    created_at: datetime

class ScratchpadFiles(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    files: Dict[UUID4, List[ScratchpadFile]] = Field(default_factory=dict)

class ScratchpadFileResponse(BaseModel):
    metadata: ScratchpadFileMetadata
    url: str