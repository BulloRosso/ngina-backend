# services/invitation.py
from datetime import datetime, timedelta
import secrets
import string
from typing import List, Optional
from uuid import UUID
from models.invitation import Invitation, InvitationCreate, InvitationStatus
from services.email import EmailService
from models.profile import Profile
import logging
from fastapi import HTTPException
from supabase import create_client, Client
import os
from fastapi import BackgroundTasks
import asyncio
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class InvitationService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        self.email_service = EmailService()

    def _generate_secret_token(self, length: int = 32) -> str:
        """Generate a secure random token"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    async def create_invitation(
        self,
        invitation_data: InvitationCreate,
        created_by: UUID,
        background_tasks: BackgroundTasks
    ) -> Invitation:
        """Create a new interview invitation"""
        try:
            # Generate token and expiry
            secret_token = self._generate_secret_token()
            expires_at = datetime.utcnow() + timedelta(days=14)

            # Prepare invitation data
            data = {
                "profile_id": str(invitation_data.profile_id),
                "created_by": str(created_by),
                "email": invitation_data.email,
                "secret_token": secret_token,
                "expires_at": expires_at.isoformat(),
                "status": InvitationStatus.ACTIVE,
                "session_count": 0
            }

            # Create invitation in database
            result = self.supabase.table("interview_invitations")\
                .insert(data)\
                .execute()

            if not result.data:
                raise Exception("Failed to create invitation")

            invitation = Invitation(**result.data[0])

            # Send invitation email
            await self._send_invitation_email(invitation)

            # Schedule expiry reminder
            # self._schedule_expiry_reminder(invitation, background_tasks)

            return invitation

        except Exception as e:
            logger.error(f"Error creating invitation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create invitation: {str(e)}"
            )
    async def get_invitations_by_creator(
        self,
        user_id: UUID,
        include_expired: bool = False
    ) -> List[Invitation]:
        """Get all invitations created by a user"""
        try:
            query = self.supabase.table("interview_invitations")\
                .select(
                    """
                    *,
                    profiles!inner(
                        first_name,
                        last_name
                    )
                    """
                )\
                .eq("created_by", str(user_id))

            if not include_expired:
                query = query.eq("status", InvitationStatus.ACTIVE)

            result = query.execute()

            return [Invitation(**inv) for inv in result.data]

        except Exception as e:
            logger.error(f"Error fetching invitations: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch invitations: {str(e)}"
            )

    async def validate_token(self, token: str) -> Optional[Invitation]:
        """Validate an invitation token and update usage if valid"""
        try:
            logger.info(f"Received token: {token}")
            
            result = self.supabase.table("interview_invitations")\
                .select("*")\
                .eq("secret_token", token)\
                .eq("status", "active")\
                .execute()

            logger.info(f"Supabase query result: {result.data}")  # Check raw data
            
            if not result.data:
                return None

            invitation = Invitation(**result.data[0])
            now = datetime.now(timezone.utc)  # Make timezone-aware

            if now > invitation.expires_at:
                await self.update_status(invitation.id, InvitationStatus.EXPIRED)
                return None

            await self._update_usage(invitation.id)

            return invitation

        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return None
    
    async def update_status(self, invitation_id: UUID, status: InvitationStatus):
        """Update invitation status"""
        try:
            self.supabase.table("interview_invitations")\
                .update({"status": status})\
                .eq("id", str(invitation_id))\
                .execute()
        except Exception as e:
            logger.error(f"Error updating invitation status: {str(e)}")
            
    async def extend_expiry(
        self,
        invitation_id: UUID,
        days: int = 14
    ) -> Invitation:
        """Extend the expiry of an invitation"""
        try:
            new_expiry = datetime.utcnow() + timedelta(days=days)

            result = self.supabase.table("interview_invitations")\
                .update({
                    "expires_at": new_expiry.isoformat(),
                    "status": InvitationStatus.ACTIVE
                })\
                .eq("id", str(invitation_id))\
                .execute()

            if not result.data:
                raise Exception("Invitation not found")

            invitation = Invitation(**result.data[0])

            # Send notification email
            await self._send_extension_email(invitation)

            return invitation

        except Exception as e:
            logger.error(f"Error extending invitation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to extend invitation: {str(e)}"
            )

    async def revoke_invitation(self, invitation_id: UUID) -> bool:
        """Revoke an invitation"""
        try:
            result = self.supabase.table("interview_invitations")\
                .update({"status": InvitationStatus.REVOKED})\
                .eq("id", str(invitation_id))\
                .execute()

            if not result.data:
                return False

            invitation = Invitation(**result.data[0])
            await self._send_revocation_email(invitation)

            return True

        except Exception as e:
            logger.error(f"Error revoking invitation: {str(e)}")
            return False

    async def _update_usage(self, invitation_id: UUID):
        """Update last_used_at and increment session_count"""
        try:
            self.supabase.table("interview_invitations")\
                .update({
                    "last_used_at": datetime.utcnow().isoformat(),
                    "session_count": self.supabase.raw(
                        'session_count + 1'
                    )
                })\
                .eq("id", str(invitation_id))\
                .execute()
        except Exception as e:
            logger.error(f"Error updating usage: {str(e)}")

    async def _send_invitation_email(self, invitation: Invitation):
        """Send initial invitation email"""
        profile_data = await self._get_profile(invitation.profile_id)
        if profile_data:
            logger.info(profile_data)
            profile = Profile(**profile_data)
            await self.email_service.send_interview_invitation(
                to_email=invitation.email,
                profile_name=f"{profile.first_name} {profile.last_name}",
                token=invitation.secret_token,
                expires_at=invitation.expires_at
            )

    async def _send_expiry_reminder(self, invitation: Invitation):
        """Send reminder email about upcoming expiry"""
        profile = await self._get_profile(invitation.profile_id)
        if profile:
            await self.email_service.send_expiry_reminder(
                to_email=invitation.email,
                profile_name=f"{profile.first_name} {profile.last_name}",
                expires_at=invitation.expires_at
            )

    async def _get_profile(self, profile_id: UUID):
        """Helper to get profile details"""
        try:
            result = self.supabase.table("profiles")\
                .select("*")\
                .eq("id", str(profile_id))\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error fetching profile: {str(e)}")
            return None

    def _schedule_expiry_reminder(
        self,
        invitation: Invitation,
        background_tasks: BackgroundTasks
    ):
        """Schedule a reminder email for 2 days before expiry"""
        try:
            # Calculate reminder time
            reminder_time = invitation.expires_at - timedelta(days=2)
            now = datetime.utcnow()

            # If reminder time is in the past, don't schedule
            if reminder_time <= now:
                logger.info(f"Skipping reminder for invitation {invitation.id} - reminder time already passed")
                return

            # Schedule the reminder task
            background_tasks.add_task(
                self._send_expiry_reminder_task,
                invitation=invitation,
                scheduled_time=reminder_time
            )

            logger.info(f"Scheduled reminder for invitation {invitation.id} at {reminder_time}")

        except Exception as e:
            logger.error(f"Failed to schedule reminder: {str(e)}")
            # Don't raise the exception - we don't want to fail the invitation creation
            # just because the reminder scheduling failed

    async def _send_expiry_reminder_task(
        self,
        invitation: Invitation,
        scheduled_time: datetime
    ):
        """Background task to send expiry reminder"""
        try:
            # Wait until scheduled time
            now = datetime.utcnow()
            if scheduled_time > now:
                wait_seconds = (scheduled_time - now).total_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

            # Verify invitation is still active
            result = self.supabase.table("interview_invitations")\
                .select("status")\
                .eq("id", str(invitation.id))\
                .execute()

            if not result.data or result.data[0]['status'] != InvitationStatus.ACTIVE:
                logger.info(f"Skipping reminder for invitation {invitation.id} - no longer active")
                return

            # Send reminder email
            await self.email_service.send_expiry_reminder(
                to_email=invitation.email,
                profile_name=f"{invitation.profile_first_name} {invitation.profile_last_name}",
                expires_at=invitation.expires_at
            )

            logger.info(f"Sent expiry reminder for invitation {invitation.id}")

        except Exception as e:
            logger.error(f"Error sending expiry reminder: {str(e)}")