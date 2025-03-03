# models/accounting.py
from typing import List, Optional
from pydantic import BaseModel, UUID4, validator
from datetime import datetime
from enum import Enum

class TransactionType(str, Enum):
    RUN = "run"
    REFILL = "refill"
    OTHER = "other"

class ChargeRequest(BaseModel):
    credits: int
    description: Optional[str] = None
    run_id: Optional[UUID4] = None
    agent_id: UUID4

    @validator('credits')
    def credits_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('credits must be positive')
        return v

    @validator('agent_id')
    def agent_id_must_be_present(cls, v):
        if v is None:
            raise ValueError('agent_id is required')
        return v

class RefillRequest(BaseModel):
    credits: int
    description: Optional[str] = None

    @validator('credits')
    def credits_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('credits must be positive')
        return v

class BalanceResponse(BaseModel):
    user_id: UUID4
    balance: int
    timestamp: datetime

class AgentUsage(BaseModel):
    agent_id: UUID4
    total_credits: int
    run_count: int
    avg_credits_per_run: float
    agent_title_en: Optional[str] = None

class ReportResponse(BaseModel):
    user_id: UUID4
    interval: str
    start_date: datetime
    end_date: datetime
    total_credits: int
    credits_remaining: int
    agents: List[AgentUsage]

class Transaction(BaseModel):
    id: UUID4
    timestamp: datetime
    user_id: UUID4
    agent_id: Optional[UUID4] = None
    run_id: Optional[UUID4] = None
    type: TransactionType
    credits: int
    balance: int
    description: Optional[str] = None