# api/v1/invitations.py
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import List, Optional
from uuid import UUID
from models.invitation import (
    Invitation,
    InvitationCreate,
    InvitationUpdate,
    InvitationStatus,
    InvitationWithProfile
)
from services.invitation import InvitationService
from dependencies.auth import get_current_user
import logging
from pydantic import BaseModel, EmailStr
from datetime import datetime
from services.email import EmailService

router = APIRouter(prefix="/invitations", tags=["invitations"])
logger = logging.getLogger(__name__)

class WaitlistEntry(BaseModel):
    email: EmailStr
    
@router.post("")
async def create_invitation(
    invitation: InvitationCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
) -> Invitation:
    """Create a new interview invitation"""
    try:
        service = InvitationService()
        return await service.create_invitation(
            invitation_data=invitation,
            created_by=current_user["sub"],
            background_tasks=background_tasks
        )
    except Exception as e:
        logger.error(f"Error creating invitation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get("/dashboard")
async def get_invitations(
    include_expired: bool = Query(False),
    include_profile: bool = Query(True),
    current_user: UUID = Depends(get_current_user)
) -> List[InvitationWithProfile | Invitation]:
    """Get all invitations for the dashboard"""
    service = InvitationService()
    return await service.get_invitations_by_creator(
        user_id=current_user,
        include_expired=include_expired,
        include_profile=include_profile
    )

@router.get("/validate")
async def validate_invitation_token(token: str = Query(...)) -> Optional[Invitation]:
    try:
        service = InvitationService()
        logger.info(f"Validating token: {token}")

        invitation = await service.validate_token(token)
        logger.info(f"Validation result: {invitation}")

        if not invitation:
            logger.info("No invitation found")
            raise HTTPException(
                status_code=404,
                detail="Invalid or expired invitation token"
            )
        return invitation
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        raise

@router.post("/{invitation_id}/extend")
async def extend_invitation(
    invitation_id: UUID,
    days: int = Query(default=14, ge=1, le=30),
    current_user: dict = Depends(get_current_user)
) -> Invitation:
    """Extend an invitation's expiry date"""
    try:
        service = InvitationService()

        # Verify ownership
        invitation = await service.get_invitation(invitation_id)
        if str(invitation.created_by) != current_user["sub"]:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to extend this invitation"
            )

        return await service.extend_expiry(invitation_id, days)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extending invitation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.post("/{invitation_id}/revoke", status_code=204)
async def revoke_invitation(
    invitation_id: UUID,
    current_user: UUID = Depends(get_current_user)
) -> None:
    """Revoke an invitation"""
    try:
        service = InvitationService()
        # Get invitation first to verify it exists
        invitation = await service.get_invitation(invitation_id)

        # Check ownership using UUID comparison
        if invitation.created_by != current_user:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to revoke this invitation"
            )

        await service.revoke_invitation(invitation_id, current_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking invitation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get("/stats")
async def get_stats(current_user: UUID = Depends(get_current_user)) -> dict:
    """Get invitation statistics for the current user"""
    service = InvitationService()
    return await service.get_invitation_stats(current_user)

    
@router.get("/{invitation_id}/sessions")
async def get_invitation_sessions(
    invitation_id: UUID,
    current_user: dict = Depends(get_current_user)
) -> List[dict]:
    """Get all interview sessions for an invitation"""
    try:
        service = InvitationService()

        # Verify ownership
        invitation = await service.get_invitation(invitation_id)
        if str(invitation.created_by) != current_user["sub"]:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to view these sessions"
            )

        return await service.get_invitation_sessions(invitation_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting invitation sessions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.post("/waitinglist")
async def join_waitlist(entry: WaitlistEntry):
    """Add user to waitlist and send notifications"""
    try:
        email_service = EmailService()
        current_time = datetime.utcnow()

        # Send notification to manufacturer
        await email_service.send_waitlist_notification_manufacturer(
            entry.email,
            current_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        )

        # Send confirmation to user
        await email_service.send_waitlist_notification_user(entry.email)

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error processing waitlist entry: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )