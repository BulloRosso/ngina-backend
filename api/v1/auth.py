# api/v1/auth.py
from fastapi import APIRouter, HTTPException, Request, Depends, Header
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from datetime import datetime, timedelta
from config.jwt import create_access_token
from supabase import create_client
import os
import bcrypt
from services.email import EmailService
import random
import string
from config.jwt import decode_token
import logging
from typing import Dict, Optional
import json

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

supabase = create_client(
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_KEY")
)

class ProfileUpdate(BaseModel):
    profile: Dict

async def get_current_user(authorization: str = Header(None)) -> str:
    """Get current user from authorization header"""
    if not authorization:
        logger.error("No authorization header provided")
        raise HTTPException(
            status_code=401,
            detail="No authorization header"
        )

    try:
        logger.debug(f"Processing authorization header: {authorization[:20]}...")
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            logger.error(f"Invalid authentication scheme: {scheme}")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication scheme"
            )

        logger.debug("Attempting to decode token...")
        payload = decode_token(token)
        if not payload:
            logger.error("Token decode returned None")
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

        user_id = payload.get("sub")
        if not user_id:
            logger.error("No user ID in token payload")
            raise HTTPException(
                status_code=401,
                detail="Invalid token payload"
            )

        logger.debug(f"Successfully validated token for user: {user_id}")
        return user_id
    except ValueError as e:
        logger.error(f"Invalid authorization header format: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format"
        )
    except Exception as e:
        logger.error(f"Error validating token: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token"
        )

def generate_verification_code():
    return ''.join(random.choices(string.digits, k=8))
    
class LoginRequest(BaseModel):
    email: str
    password: str
    
class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str

class VerificationRequest(BaseModel):
    code: str
    user_id: str
    
# api/v1/auth.py
@router.post("/signup")
async def signup(request: SignupRequest):
    try:
        # Check if user exists
        result = supabase.table("users").select("*").eq("email", request.email).execute()
        if result.data:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Generate verification code
        verification_code = generate_verification_code()

        # Create user with verification code in profile
        user_data = {
            "first_name": request.first_name,
            "last_name": request.last_name,
            "email": request.email,
            "password": bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
            "profile": {
                "signup_secret": verification_code,
                "is_validated_by_email": False
            }
        }

        result = supabase.table("users").insert(user_data).execute()
        user = result.data[0]

        # Send verification email (synchronously)
        email_service = EmailService()
        email_service.send_verification_email(request.email, verification_code)  # Removed await

        # Create access token
        access_token = create_access_token(data={"sub": user["id"], "email": user["email"]})

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "is_validated": False
            }
        }
    except Exception as e:
        print(f"Signup error: {str(e)}")  # Add debug logging
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/validation-status/{user_id}")
async def check_validation_status(user_id: str):
    """Check if a user's email is validated"""
    try:
        # Query user from Supabase
        result = supabase.table("users").select("profile").eq("id", user_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        user = result.data[0]
        profile = user.get("profile", {})

        # Check validation status from profile JSONB
        is_validated = profile.get("is_validated_by_email", False)

        return {
            "is_validated": is_validated,
            "user_id": user_id
        }

    except Exception as e:
        logger.error(f"Error checking validation status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check validation status: {str(e)}"
        )
        
@router.post("/verify-email")
async def verify_email(verification_data: VerificationRequest):
    try:
        # Get user
        result = supabase.table("users").select("*").eq(
            "id", verification_data.user_id
        ).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        user = result.data[0]
        profile = user.get("profile", {})

        # Check verification code
        if profile.get("signup_secret") != verification_data.code:
            return {"verified": False}

        # Update user profile
        profile["is_validated_by_email"] = True
        supabase.table("users").update(
            {"profile": profile}
        ).eq("id", verification_data.user_id).execute()

        return {"verified": True}
    except Exception as e:
        print(f"Verification error: {str(e)}")  # Add debug logging
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/resend-verification")
async def resend_verification(user_id: str):
    try:
        # Get user
        result = supabase.table("users").select("*").eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        user = result.data[0]

        # Generate new verification code
        verification_code = generate_verification_code()

        # Update user profile
        profile = user.get("profile", {})
        profile["signup_secret"] = verification_code
        supabase.table("users").update({"profile": profile}).eq("id", user_id).execute()

        # Send new verification email
        email_service = EmailService()
        await email_service.send_verification_email(user["email"], verification_code)

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login")
async def login(login_data: LoginRequest):  # Use Pydantic model for validation
    try:
        print(f"Login attempt for email: {login_data.email}")  # Debug logging

        # Get user from Supabase
        result = supabase.table("users").select("*").eq("email", login_data.email).execute()

        if not result.data:
            raise HTTPException(
                status_code=401, 
                detail="Invalid email or password"
            )

        user = result.data[0]

        # Verify password
        is_valid = bcrypt.checkpw(
            login_data.password.encode('utf-8'),
            user["password"].encode('utf-8')
        )

        if not is_valid:
            raise HTTPException(
                status_code=401, 
                detail="Invalid email or password"
            )

        # Create access token
        access_token = create_access_token(
            data={"sub": user["id"], "email": user["email"]}
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "first_name": user["first_name"],
                "last_name": user["last_name"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {str(e)}")  # Debug logging
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/profile/{user_id}")
async def get_user_profile(
    user_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get user profile settings"""
    try:
        logger.debug(f"Getting profile for user ID: {user_id}")

        # Verify user is accessing their own profile
        if current_user != user_id:
            logger.warning(f"User {current_user} attempted to access profile of {user_id}")
            raise HTTPException(
                status_code=403,
                detail="Cannot access another user's profile"
            )

        result = supabase.table("users").select("profile").eq("id", user_id).execute()

        if not result.data:
            logger.warning(f"No profile found for user {user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        profile_data = result.data[0].get("profile", {})

        # Ensure default fields exist
        profile_data.setdefault("signup_secret", "")
        profile_data.setdefault("is_validated_by_email", False)
        profile_data.setdefault("narrator_perspective", "ego")
        profile_data.setdefault("narrator_verbosity", "normal")
        profile_data.setdefault("narrator_style", "neutral")

        logger.debug(f"Successfully retrieved profile for user {user_id}")
        return {"profile": profile_data}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/profile")
async def update_user_profile(
    profile_update: ProfileUpdate,
    current_user: str = Depends(get_current_user)
):
    """Update user profile settings"""
    try:
        logger.info(f"Updating profile for user ID: {current_user}")

        # Get current profile to merge with new settings
        current_result = supabase.table("users").select("profile").eq("id", current_user).execute()

        if not current_result.data:
            logger.warning(f"No profile found for user {current_user}")
            raise HTTPException(status_code=404, detail="User not found")

        current_profile = current_result.data[0].get("profile", {})

        # Ensure required fields are preserved
        updated_profile = {
            "signup_secret": current_profile.get("signup_secret", ""),
            "is_validated_by_email": current_profile.get("is_validated_by_email", False),
            **profile_update.profile
        }

        # Update profile in database
        result = supabase.table("users").update(
            {"profile": updated_profile}
        ).eq("id", current_user).execute()

        if not result.data:
            logger.error(f"Failed to update profile for user {current_user}")
            raise HTTPException(status_code=404, detail="Failed to update profile")

        logger.info(f"Successfully updated profile for user {current_user}")
        return {"message": "Profile updated successfully", "profile": updated_profile}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))