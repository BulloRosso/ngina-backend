# models/invitation.py
from pydantic import BaseModel, EmailStr, UUID4
from datetime import datetime
from typing import Optional
from enum import Enum

class InvitationStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"

class InvitationCreate(BaseModel):
    profile_id: UUID4
    email: EmailStr

class InvitationUpdate(BaseModel):
    expires_at: Optional[datetime]
    status: Optional[InvitationStatus]

class Invitation(BaseModel):
    id: UUID4
    profile_id: UUID4
    created_by: UUID4
    email: EmailStr
    secret_token: str
    expires_at: datetime
    last_used_at: Optional[datetime]
    status: InvitationStatus
    session_count: int
    created_at: datetime
    updated_at: datetime

class InvitationWithProfile(Invitation):
    profile_first_name: str
    profile_last_name: str