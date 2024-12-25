# services/user_management.py
from typing import Optional, Dict, Any
from pydantic import BaseModel
from supabase import create_client, Client
import os
import logging
import bcrypt
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)

class UserData(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str

class UserManagementService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

    async def create_user(self, user_data: UserData) -> Dict[str, Any]:
        """Create a new user using Supabase Auth API"""
        try:
            logger.debug(f"Creating user with email: {user_data.email}")

            # Create user through Supabase Auth API
            response = self.supabase.auth.admin.create_user({
                "email": user_data.email,
                "password": user_data.password,
                "email_confirm": False,  # Skip email confirmation for now
                "user_metadata": {
                    "first_name": user_data.first_name,
                    "last_name": user_data.last_name
                }
            })

            if not response.user:
                raise Exception("Failed to create user")

            return {
                "id": response.user.id,
                "email": response.user.email,
                "first_name": response.user.user_metadata.get("first_name"),
                "last_name": response.user.user_metadata.get("last_name")
            }

        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise

    async def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """Login user using Supabase Auth API"""
        try:
            logger.debug(f"Attempting login for email: {email}")

            # Login through Supabase Auth API
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if not response.user:
                raise Exception("Invalid credentials")

            return {
                "id": response.user.id,
                "email": response.user.email,
                "first_name": response.user.user_metadata.get("first_name"),
                "last_name": response.user.user_metadata.get("last_name"),
                "access_token": response.session.access_token
            }

        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            raise

    async def request_password_reset(self, email: str) -> bool:
        """Request password reset through Supabase Auth API"""
        try:
            await self.supabase.auth.reset_password_email(email)
            return True
        except Exception as e:
            logger.error(f"Password reset request error: {str(e)}")
            raise

    async def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password using token through Supabase Auth API"""
        try:
            await self.supabase.auth.update_user({
                "password": new_password
            }, jwt=token)
            return True
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            raise

    async def get_user_by_id(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get user by ID using Supabase Auth API"""
        try:
            logger.info("Trying to get user by ID " + str(user_id))
            response = self.supabase.auth.admin.get_user_by_id(str(user_id))

            if not response.user:
                return None

            return {
                "id": response.user.id,
                "email": response.user.email,
                "first_name": response.user.user_metadata.get("first_name"),
                "last_name": response.user.user_metadata.get("last_name")
            }
        except Exception as e:
            logger.error(f"Error fetching user: {str(e)}")
            raise

    async def update_user_profile(self, user_id: UUID, profile_data: Dict[str, Any]) -> bool:
        """Update user metadata through Supabase Auth API"""
        try:
            await self.supabase.auth.admin.update_user_by_id(
                str(user_id),
                {"user_metadata": profile_data}
            )
            return True
        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}")
            raise

    async def verify_email(self, user_id: UUID, verification_code: str) -> bool:
        """Verify user's email"""
        try:
            # Get current user data
            user = await self.get_user_by_id(user_id)
            if not user:
                return False

            # For now, just update the user metadata to mark as verified
            # In production, you'd want to verify the code matches
            await self.update_user_profile(user_id, {
                "is_validated_by_email": True
            })
            return True

        except Exception as e:
            logger.error(f"Error verifying email: {str(e)}")
            raise

    async def check_validation_status(self, user_id: UUID) -> bool:
        """Check if user's email is validated"""
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                return False

            # Get user metadata from Supabase
            response = self.supabase.auth.admin.get_user_by_id(str(user_id))
            metadata = response.user.user_metadata or {}

            return metadata.get("is_validated_by_email", False)

        except Exception as e:
            logger.error(f"Error checking validation status: {str(e)}")
            raise

    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile information"""
        try:
            response = self.supabase.auth.admin.get_user_by_id(user_id)
            if not response.user:
                return None

            metadata = response.user.user_metadata or {}
            metadata.setdefault("signup_secret", "")
            metadata.setdefault("is_validated_by_email", False)
            metadata.setdefault("narrator_perspective", "ego")
            metadata.setdefault("narrator_verbosity", "normal")
            metadata.setdefault("narrator_style", "neutral")

            return {"profile": metadata}
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            raise

    async def update_user_profile_settings(self, user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile settings"""
        try:
            # Get current user metadata first
            current_user = await self.get_user_by_id(UUID(user_id))
            if not current_user:
                raise Exception("User not found")

            # Get full user data to access metadata
            response = self.supabase.auth.admin.get_user_by_id(user_id)
            current_metadata = response.user.user_metadata or {}

            # Preserve required fields
            updated_metadata = {
                "signup_secret": current_metadata.get("signup_secret", ""),
                "is_validated_by_email": current_metadata.get("is_validated_by_email", False),
                **profile_data
            }

            # Update user metadata
            await self.supabase.auth.admin.update_user_by_id(
                user_id,
                {"user_metadata": updated_metadata}
            )

            return {"message": "Profile updated successfully", "profile": updated_metadata}
        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}")
            raise