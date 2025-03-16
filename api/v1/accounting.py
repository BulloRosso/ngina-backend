# api/v1/accounting.py
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import UUID4
import logging
import os
from models.accounting import Transaction, BalanceResponse, ChargeRequest, RefillRequest, ReportResponse
from services.accounting import AccountingService
from dependencies.auth import get_current_user_dependency

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/accounting", tags=["accounting"])

# Authentication dependency
async def verify_api_key(x_ngina_key: str = Header(None)):
    if x_ngina_key != os.getenv("NGINA_ACCOUNTING_KEY"):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    return x_ngina_key

# API Routes
@router.get("/balance/{user_id}", response_model=BalanceResponse, dependencies=[Depends(verify_api_key)])
async def get_balance(user_id: UUID4):
    """
    Returns the current balance for a user.
    """
    service = AccountingService()
    return await service.get_balance(user_id)

@router.post("/charge/{user_id}", response_model=Transaction, dependencies=[Depends(verify_api_key)])
async def charge_user(user_id: UUID4, charge_data: ChargeRequest):
    """
    Charges a user for using an agent.
    """
    service = AccountingService()
    logger.info(f"Charging user {user_id} for agent {charge_data.agent_id} with amount {charge_data.credits}")
    return await service.charge_user(user_id, charge_data)

@router.post("/refill/{user_id}", response_model=Transaction, dependencies=[Depends(verify_api_key)])
async def refill_user(user_id: UUID4, refill_data: RefillRequest):
    """
    Adds credits to a user's balance.
    """
    service = AccountingService()
    return await service.refill_user(user_id, refill_data)

@router.get("/report/{interval}", response_model=ReportResponse)
async def get_report(interval: str, user_id: UUID4 = Depends(get_current_user_dependency)):
    """
    Generates a usage report for the specified interval.
    Interval must be one of: 'day', 'month', 'year'.
    Uses JWT authentication to verify the user.
    """
    service = AccountingService()
    return await service.get_report(user_id, interval)