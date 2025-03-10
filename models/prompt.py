# models/prompt.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, UUID4, field_validator
import re

class PromptBase(BaseModel):
    name: str
    prompt_text: str
    version: Optional[int] = 1
    is_active: Optional[bool] = False

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('name must contain only letters, numbers, and underscores')
        return v

class PromptCreate(PromptBase):
    pass

class Prompt(PromptBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    created_at: datetime

class PromptCompare(BaseModel):
    prompts: List[Prompt]