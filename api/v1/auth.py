# api/v1/auth.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from config.jwt import create_access_token
from supabase import create_client
import os
import bcrypt
from services.email import EmailService
import random
import string

router = APIRouter(prefix="/auth", tags=["auth"])

supabase = create_client(
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_KEY")
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