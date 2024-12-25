# services/invitation.py
from datetime import datetime, timedelta
import secrets
import string
from typing import List, Optional
from uuid import UUID
from models.invitation import Invitation, InvitationCreate, InvitationStatus, InvitationWithProfile
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

    async def get_invitation_stats(self, user_id: UUID) -> dict:
        """Get statistics about invitations for a user"""
        try:
            now = datetime.now(timezone.utc)
            user_id_str = str(user_id)  # Convert UUID to string for Supabase queries

            # Get total count
            total_result = self.supabase.table("interview_invitations")\
                .select("*", count="exact")\
                .eq("created_by", user_id_str)\
                .execute()

            # Get active count
            active_result = self.supabase.table("interview_invitations")\
                .select("*", count="exact")\
                .eq("created_by", user_id_str)\
                .eq("status", InvitationStatus.ACTIVE.value)\
                .gte("expires_at", now.isoformat())\
                .execute()

            # Get expired count
            expired_result = self.supabase.table("interview_invitations")\
                .select("*", count="exact")\
                .eq("created_by", user_id_str)\
                .eq("status", InvitationStatus.ACTIVE.value)\
                .lt("expires_at", now.isoformat())\
                .execute()

            # Get revoked count
            revoked_result = self.supabase.table("interview_invitations")\
                .select("*", count="exact")\
                .eq("created_by", user_id_str)\
                .eq("status", InvitationStatus.REVOKED.value)\
                .execute()

            return {
                "total_invitations": total_result.count or 0,
                "active_invitations": active_result.count or 0,
                "expired_invitations": expired_result.count or 0,
                "revoked_invitations": revoked_result.count or 0
            }

        except Exception as e:
            logger.error(f"Error getting invitation stats: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get invitation stats: {str(e)}"
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

    async def get_invitations_by_creator(
        self,
        user_id: UUID,
        include_expired: bool = False,
        include_profile: bool = False
    ) -> List[Invitation | InvitationWithProfile]:
        """
        Get all invitations created by a user.
        Args:
            user_id: The UUID of the user who created the invitations
            include_expired: Whether to include expired invitations
            include_profile: Whether to include profile details
        """
        try:
            logger.debug(f"Fetching invitations for user {user_id}")

            # Build base query
            query = self.supabase.table("interview_invitations")

            # Select fields based on whether we need profile info
            if include_profile:
                query = query.select(
                    "*, profiles!inner(first_name,last_name)"
                )
            else:
                query = query.select("*")

            # Add filters
            query = query.eq("created_by", str(user_id))

            # If not including expired, only show active invitations
            if not include_expired:
                now = datetime.now(timezone.utc)
                query = query.or_(
                    f"and(status.eq.{InvitationStatus.ACTIVE.value},expires_at.gt.{now.isoformat()})"
                )

            # Execute query
            result = query.execute()

            if not result.data:
                return []

            invitations = []
            for inv in result.data:
                # Update status based on expiry date if not already revoked
                current_status = inv["status"]
                expires_at = datetime.fromisoformat(inv["expires_at"].replace('Z', '+00:00'))

                if current_status != InvitationStatus.REVOKED.value:
                    if expires_at < datetime.now(timezone.utc):
                        current_status = InvitationStatus.EXPIRED.value

                # Base invitation data
                invitation_data = {
                    "id": UUID(inv["id"]),
                    "profile_id": UUID(inv["profile_id"]),
                    "created_by": UUID(inv["created_by"]),
                    "email": inv["email"],
                    "secret_token": inv["secret_token"],
                    "expires_at": expires_at,
                    "last_used_at": inv["last_used_at"],
                    "status": InvitationStatus(current_status),
                    "session_count": 0  # We'll implement session counting later
                }

                if include_profile and "profiles" in inv:
                    # Create InvitationWithProfile if profile data is included
                    invitation_data.update({
                        "profile_first_name": inv["profiles"]["first_name"],
                        "profile_last_name": inv["profiles"]["last_name"]
                    })
                    invitations.append(InvitationWithProfile(**invitation_data))
                else:
                    # Create base Invitation otherwise
                    invitations.append(Invitation(**invitation_data))

            return invitations

        except Exception as e:
            logger.error(f"Error fetching invitations: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch invitations: {str(e)}"
            )

    async def revoke_invitation(self, invitation_id: UUID, current_user_id: UUID) -> None:
        """Revoke an invitation"""
        try:
            # Update the invitation status
            result = self.supabase.table("interview_invitations")\
                .update({"status": InvitationStatus.REVOKED.value})\
                .eq("id", str(invitation_id))\
                .execute()

            if not result.data:
                raise HTTPException(
                    status_code=404,
                    detail="Invitation not found"
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error revoking invitation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to revoke invitation: {str(e)}"
            )

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
            
    async def get_invitation(self, invitation_id: UUID) -> Invitation:
        """Get a single invitation by ID"""
        try:
            result = self.supabase.table("interview_invitations")\
                .select("*")\
                .eq("id", str(invitation_id))\
                .execute()
    
            if not result.data:
                raise HTTPException(
                    status_code=404,
                    detail="Invitation not found"
                )
    
            inv = result.data[0]
            return Invitation(
                id=UUID(inv["id"]),
                profile_id=UUID(inv["profile_id"]),
                created_by=UUID(inv["created_by"]),  # Add created_by
                email=inv["email"],
                secret_token=inv["secret_token"],
                expires_at=inv["expires_at"],
                last_used_at=inv["last_used_at"],
                status=InvitationStatus(inv["status"]),
                session_count=0  # TODO: Implement session counting
            )
    
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching invitation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch invitation: {str(e)}"
            )
    
    async def revoke_invitation(self, invitation_id: UUID, current_user_id: UUID) -> None:
        """Revoke an invitation"""
        try:
            # First, get the invitation to check if it exists and belongs to the user
            invitation = await self.get_invitation(invitation_id)
    
            # Check if the invitation belongs to the current user
            if invitation.created_by != current_user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to revoke this invitation"
                )
    
            # Check if invitation is already revoked
            if invitation.status == InvitationStatus.REVOKED:
                raise HTTPException(
                    status_code=400,
                    detail="Invitation is already revoked"
                )
    
            # Update the invitation status
            result = self.supabase.table("interview_invitations")\
                .update({"status": InvitationStatus.REVOKED.value})\
                .eq("id", str(invitation_id))\
                .eq("created_by", str(current_user_id))\
                .execute()
    
            if not result.data:
                raise HTTPException(
                    status_code=404,
                    detail="Invitation not found"
                )
    
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error revoking invitation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to revoke invitation: {str(e)}"
            )