# api/v1/auth.py
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Optional, Any
from pydantic import BaseModel
from uuid import UUID
import logging
import os
from services.usermanagement import UserManagementService, UserData
from dependencies.auth import get_current_user
from supabase import create_client, Client

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

@router.post("/signup")
async def signup(request: SignupRequest):
    try:
        service = UserManagementService()
        user = await service.create_user(UserData(
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            password=request.password
        ))

        return {
            "user": user,
            "message": "User created successfully"
        }
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
async def login(login_data: LoginRequest):
    try:
        service = UserManagementService()
        result = await service.login_user(login_data.email, login_data.password)

        supabase_client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

        # Get user verification status
        user_response = supabase_client.auth.admin.get_user_by_id(result["id"])
        is_validated = False
        mfa_required = False
        mfa_data = None

        if user_response.user.identities:
            identity = user_response.user.identities[0]
            is_validated = identity.identity_data['email_verified']

            # Check if MFA needs to be set up
            try:
                qr_response = supabase_client.auth.api.generate_mfa_qr_code(
                    access_token=result["access_token"]
                )
                if qr_response.get("qr_code"):
                    mfa_required = True
                    mfa_data = {
                        'qr_code': qr_response["qr_code"],
                        'secret': qr_response.get("secret", "")
                    }
            except Exception as e:
                logger.error(f"Error generating MFA QR code: {str(e)}")

        return {
            "access_token": result["access_token"],
            "token_type": "bearer",
            "user": {
                "id": result["id"],
                "email": result["email"],
                "first_name": result["first_name"],
                "last_name": result["last_name"],
                "is_validated": is_validated
            },
            "mfa_required": mfa_required,
            "mfa_data": mfa_data
        }
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
@router.post("/verify-email")
async def verify_email(verification_data: VerificationRequest):
    try:
        service = UserManagementService()
        verified = await service.verify_email(
            UUID(verification_data.user_id),
            verification_data.code
        )
        return {"verified": verified}
    except Exception as e:
        logger.error(f"Verification error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/validation-status/{user_id}")
async def check_validation_status(user_id: str):
    try:
        supabase_client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

        user_response = supabase_client.auth.admin.get_user_by_id(user_id)
        is_validated = False

        if user_response.user.identities:
            identity = user_response.user.identities[0]
            is_validated = identity.identity_data['email_verified']

        return {
            "is_validated": is_validated,
            "user_id": user_id
        }
    except Exception as e:
        logger.error(f"Validation status check error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/verify-mfa")
async def verify_mfa(user_id: str, totp_code: str, access_token: str):
    try:
        supabase_client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

        verify_response = supabase_client.auth.api.verify_mfa({
            "access_token": access_token,
            "totp_code": totp_code
        })

        if not verify_response:
            raise HTTPException(status_code=400, detail="Invalid MFA code")

        return {"success": True, "message": "MFA setup successful"}
    except Exception as e:
        logger.error(f"MFA verification error: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid MFA code")
        
@router.post("/request-password-reset")
async def request_password_reset(request: PasswordResetRequest):
    try:
        service = UserManagementService()
        await service.request_password_reset(request.email)

        # For security, always return success even if email doesn't exist
        return {"message": "If the email exists, a reset link has been sent."}
    except Exception as e:
        logger.error(f"Password reset request error: {str(e)}")
        return {"message": "If the email exists, a reset link has been sent."}

@router.post("/reset-password")
async def reset_password(request: PasswordResetConfirm):
    try:
        service = UserManagementService()
        success = await service.reset_password(request.token, request.new_password)

        if not success:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        return {"message": "Password has been reset successfully"}
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/profile/{user_id}")
async def get_user_profile(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get user profile settings"""
    try:
        # Verify user is accessing their own profile
        if str(current_user["id"]) != user_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot access another user's profile"
            )

        service = UserManagementService()
        result = await service.get_user_profile(user_id)

        if not result:
            raise HTTPException(status_code=404, detail="User not found")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/profile")
async def update_user_profile(
    profile_update: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """Update user profile settings"""
    try:
        service = UserManagementService()
        result = await service.update_user_profile_settings(
            str(current_user["id"]),
            profile_update
        )
        return result
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    try:
        service = UserManagementService()
        # Supabase will verify the token and return user info
        user = await service.get_user_by_id(token)

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )