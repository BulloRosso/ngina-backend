# api/v1/auth.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from config.jwt import create_access_token
from supabase import create_client
import os
import bcrypt

router = APIRouter(prefix="/auth", tags=["auth"])

supabase = create_client(
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_KEY")
)

class LoginRequest(BaseModel):
    email: str
    password: str
    
class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str

@router.post("/signup")
async def signup(request: SignupRequest):
    try:
        # Check if user exists in Supabase
        result = supabase.table("users").select("*").eq("email", request.email).execute()

        if result.data:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Hash password
        hashed_password = bcrypt.hashpw(
            request.password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        # Create user in Supabase
        user_data = {
            "first_name": request.first_name,
            "last_name": request.last_name,
            "email": request.email,
            "password": hashed_password
        }

        result = supabase.table("users").insert(user_data).execute()
        user = result.data[0]

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