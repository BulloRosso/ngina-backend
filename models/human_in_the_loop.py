# models/human_in_the_loop.py
from pydantic import BaseModel, UUID4, Field, EmailStr
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from datetime import datetime

class HumanFeedbackStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class EmailRecipient(BaseModel):
    email: EmailStr
    name: Optional[str] = None

class EmailSettings(BaseModel):
    subject: str
    flagAsImportant: bool = False
    recipients: List[EmailRecipient]

# Fix for Pydantic v2 - Use Union with dict for better handling of optional complex types
class HumanInTheLoopCreate(BaseModel):
    workflow_id: str
    callback_url: str
    # Using Union[EmailSettings, Dict, None] allows for more flexible input validation
    email_settings: Optional[Union[EmailSettings, Dict[str, Any]]] = None
    reason: Optional[str] = None

class HumanInTheLoop(BaseModel):
    id: UUID4
    created_at: datetime
    run_id: Optional[UUID4] = None
    email_settings: Optional[Dict[str, Any]] = None
    status: HumanFeedbackStatus = HumanFeedbackStatus.PENDING
    workflow_id: Optional[str] = None
    reason: Optional[str] = None
    callback_url: Optional[str] = None