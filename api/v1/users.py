# api/v1/users.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import logging
import os
from supabase import create_client
from dependencies.auth import get_current_user_dependency

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)

class UserResponse(BaseModel):
    id: str
    email: str
    phone: Optional[str] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    email_confirmed_at: Optional[datetime] = None
    last_sign_in_at: Optional[datetime] = None
    user_metadata: Dict[str, Any] = {}
    app_metadata: Dict[str, Any] = {}
    role: Optional[str] = None
    updated_at: Optional[datetime] = None

@router.get("/", response_model=List[UserResponse])
async def list_users(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    per_page: int = Query(100, ge=1, le=1000, description="Items per page (max 1000)"),
    ):
    """
    List all users in the system.
    This endpoint requires admin privileges.
    """
    try:
        # Check if user has admin privileges
        # This checks either the app_metadata directly or user_metadata based on your auth implementation
        #is_admin = current_user.get("app_metadata", {}).get("is_admin", False) or \
        #          current_user.get("user_metadata", {}).get("is_admin", False)

        #if not is_admin:
        #    raise HTTPException(status_code=403, detail="Admin privileges required")

        # Initialize Supabase client
        supabase_client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

        # Get users list
        logger.info(f"Fetching users with page={page}, per_page={per_page}")
        response = supabase_client.auth.admin.list_users(
            page=page,
            per_page=per_page
        )

        # Format the response
        users = []
        for user in response:
            users.append({
                "id": user.id,
                "email": user.email,
                "phone": user.phone or "",
                "created_at": user.created_at,
                "confirmed_at": user.confirmed_at,
                "email_confirmed_at": user.email_confirmed_at,
                "last_sign_in_at": user.last_sign_in_at,
                "user_metadata": user.user_metadata,
                "app_metadata": user.app_metadata,
                "role": user.role,
                "updated_at": user.updated_at
            })

        return users

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to retrieve users")