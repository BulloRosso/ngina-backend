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

router = APIRouter(prefix="/invitations", tags=["invitations"])
logger = logging.getLogger(__name__)

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
async def get_invitations_dashboard(
    include_expired: bool = False,
    current_user: dict = Depends(get_current_user)
) -> List[InvitationWithProfile]:
    """Get all invitations created by the current user"""
    try:
        service = InvitationService()
        return await service.get_invitations_by_creator(
            user_id=current_user["sub"],
            include_expired=include_expired
        )
    except Exception as e:
        logger.error(f"Error fetching invitations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
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

@router.post("/{invitation_id}/revoke")
async def revoke_invitation(
    invitation_id: UUID,
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Revoke an invitation"""
    try:
        service = InvitationService()

        # Verify ownership
        invitation = await service.get_invitation(invitation_id)
        if str(invitation.created_by) != current_user["sub"]:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to revoke this invitation"
            )

        success = await service.revoke_invitation(invitation_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Invitation not found"
            )
        return {"message": "Invitation revoked successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking invitation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get("/stats")
async def get_invitation_stats(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Get statistics about invitations"""
    try:
        service = InvitationService()
        invitations = await service.get_invitations_by_creator(
            user_id=current_user["sub"],
            include_expired=True
        )

        active_count = sum(1 for inv in invitations if inv.status == InvitationStatus.ACTIVE)
        expired_count = sum(1 for inv in invitations if inv.status == InvitationStatus.EXPIRED)
        total_sessions = sum(inv.session_count for inv in invitations)

        return {
            "total_invitations": len(invitations),
            "active_invitations": active_count,
            "expired_invitations": expired_count,
            "total_sessions": total_sessions,
            "average_sessions_per_invitation": total_sessions / len(invitations) if invitations else 0
        }
    except Exception as e:
        logger.error(f"Error getting invitation stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

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