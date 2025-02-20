# api/v1/vault.py
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import UUID
import logging
from pydantic import BaseModel
from dependencies.auth import get_current_user
from datetime import datetime
from supabase import create_client
import os

logger = logging.getLogger(__name__)

supabase = create_client(
    supabase_url = os.getenv("SUPABASE_URL"),
    supabase_key = os.getenv("SUPABASE_KEY")
)

router = APIRouter(prefix="/vault", tags=["vault"])

class CredentialCreate(BaseModel):
    service_name: str
    key_name: str
    secret_key: str

class CredentialResponse(BaseModel):
    service_name: str
    key_name: str
    secret_key: str
    user_id: UUID
    # Make optional fields that might not be returned immediately
    id: Optional[UUID] = None
    created_at: Optional[datetime] = None

@router.post("", response_model=CredentialResponse)
async def create_credential(
    credential: CredentialCreate,
    user_id: UUID = Depends(get_current_user)
):
    """Create or update a credential in the vault"""
    try:
        # Simple insert - the trigger handles upsert logic
        result = supabase.table("secure_credentials").insert({
            "user_id": str(user_id),
            "service_name": credential.service_name,
            "key_name": credential.key_name,
            "secret_key": credential.secret_key
        }).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create/update credential")

        logger.debug(f"Supabase response data: {result.data}")

        response_data = {
            "user_id": user_id,
            "service_name": credential.service_name,
            "key_name": credential.key_name,
            "secret_key": credential.secret_key
        }

        if result.data[0].get('id'):
            response_data['id'] = result.data[0]['id']
        if result.data[0].get('created_at'):
            response_data['created_at'] = result.data[0]['created_at']

        return CredentialResponse(**response_data)

    except Exception as e:
        logger.error(f"Error creating/updating credential: {str(e)}")
        logger.error(f"Result data: {result.data if 'result' in locals() else 'No result'}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create/update credential: {str(e)}"
        )

@router.get("", response_model=List[CredentialResponse])
async def list_credentials(
    user_id: UUID = Depends(get_current_user)
):
    """Get all credentials for the current user"""
    try:
        result = supabase.table("secure_credentials")\
            .select("*")\
            .eq("user_id", str(user_id))\
            .execute()

        if not result.data:
            return []

        return [CredentialResponse(**item) for item in result.data]

    except Exception as e:
        logger.error(f"Error fetching credentials: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch credentials: {str(e)}"
        )

@router.get("/{credential_id}", response_model=CredentialResponse)
async def get_credential(
    credential_id: UUID,
    user_id: UUID = Depends(get_current_user)
):
    """Get a specific credential"""
    try:
        result = supabase.table("secure_credentials")\
            .select("*")\
            .eq("id", str(credential_id))\
            .eq("user_id", str(user_id))\
            .single()\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Credential not found")

        return CredentialResponse(**result.data)

    except Exception as e:
        logger.error(f"Error fetching credential: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch credential: {str(e)}"
        )

@router.put("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: UUID,
    credential: CredentialCreate,
    user_id: UUID = Depends(get_current_user)
):
    """Update a specific credential"""
    try:
        # Verify existence and ownership
        existing = supabase.table("secure_credentials")\
            .select("*")\
            .eq("id", str(credential_id))\
            .eq("user_id", str(user_id))\
            .single()\
            .execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="Credential not found")

        # Update the credential
        result = supabase.table("secure_credentials")\
            .update({
                "service_name": credential.service_name,
                "key_name": credential.key_name,
                "secret_key": credential.secret_key
            })\
            .eq("id", str(credential_id))\
            .eq("user_id", str(user_id))\
            .execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to update credential")

        return CredentialResponse(**result.data[0])

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating credential: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update credential: {str(e)}"
        )

@router.delete("/{credential_id}")
async def delete_credential(
    credential_id: UUID,
    user_id: UUID = Depends(get_current_user)
):
    """Delete a specific credential"""
    try:
        # Verify existence and ownership
        existing = supabase.table("secure_credentials")\
            .select("*")\
            .eq("id", str(credential_id))\
            .eq("user_id", str(user_id))\
            .single()\
            .execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="Credential not found")

        # Delete the credential
        result = supabase.table("secure_credentials")\
            .delete()\
            .eq("id", str(credential_id))\
            .eq("user_id", str(user_id))\
            .execute()

        return {"message": "Credential deleted successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting credential: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete credential: {str(e)}"
        )