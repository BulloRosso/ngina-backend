# api/v1/profiles.py
from fastapi import APIRouter, HTTPException, File, Form, Query, UploadFile
from typing import Optional
from uuid import UUID
import json
import os
from datetime import datetime, date
import traceback
from models.profile import Profile, ProfileCreate
from supabase import create_client
import asyncio
from services.profile import ProfileService
from io import BytesIO
from typing import List
from models.profile import Profile
from io import BytesIO
import logging
from pydantic import BaseModel
from typing import List, Optional

logger = logging.getLogger(__name__)

class ProfileRating(BaseModel):
    completeness: float
    memories_count: int
    memories_with_images: int
    rating: str
    
router = APIRouter(prefix="/profiles", tags=["profiles"])

# Initialize Supabase client
supabase = create_client(
    supabase_url = os.getenv("SUPABASE_URL"),
    supabase_key = os.getenv("SUPABASE_KEY")
)

@router.get("")
async def list_profiles() -> List[Profile]:
    """Get all profiles"""
    try:
        profiles = await ProfileService.get_all_profiles()
        return profiles
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch profiles: {str(e)}")
        
@router.get("/user/{user_id}")
async def get_profiles_for_user(user_id: UUID) -> List[Profile]:
    """Get all profiles for a specific user"""
    try:
        service = ProfileService()

        # Get profiles only for the specified user
        result = service.supabase.table("profiles")\
            .select("*")\
            .eq("user_id", str(user_id))\
            .order('updated_at', desc=True)\
            .execute()

        profiles = []
        for profile_data in result.data:
            try:
                # Convert date strings
                if isinstance(profile_data['date_of_birth'], str):
                    profile_data['date_of_birth'] = datetime.fromisoformat(
                        profile_data['date_of_birth']
                    ).date()

                if isinstance(profile_data['created_at'], str):
                    profile_data['created_at'] = datetime.fromisoformat(
                        profile_data['created_at']
                    )

                if isinstance(profile_data['updated_at'], str):
                    profile_data['updated_at'] = datetime.fromisoformat(
                        profile_data['updated_at']
                    )

                # Add session count to metadata
                session_count_result = service.supabase.table('interview_sessions')\
                    .select('id', count='exact')\
                    .eq('profile_id', profile_data['id'])\
                    .execute()

                if not profile_data.get('metadata'):
                    profile_data['metadata'] = {}

                profile_data['metadata']['session_count'] = session_count_result.count

                profiles.append(Profile(**profile_data))
            except Exception as e:
                logger.error(f"Error converting profile data: {str(e)}")
                logger.error(f"Problematic profile data: {profile_data}")
                continue

        return profiles

    except Exception as e:
        logger.error(f"Error fetching user profiles: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch user profiles: {str(e)}"
        )

@router.post("")
async def create_profile(
    profile_image: UploadFile = File(...),
    profile: str = Form(...),
    language: str = Form("en")  # Add language parameter with default "en"
):
    try:
        profile_data = json.loads(profile)
        
        first_name = profile_data.get("first_name")
        last_name = profile_data.get("last_name")
        user_id = profile_data.get("user_id")
        
        if not first_name or not last_name or not user_id:  # Update validation
            raise ValueError("first_name, last_name, and user_id are required.")
        
        profile_data["date_of_birth"] = datetime.strptime(profile_data["date_of_birth"], "%Y-%m-%d").date()

        if not first_name or not last_name:
            raise ValueError("Both first_name and last_name are required.")

        # Sanitize filename - handle non-ASCII characters
        def sanitize_filename(s: str) -> str:
            # Replace umlauts and special characters
            replacements = {
                'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
                'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
                'é': 'e', 'è': 'e', 'ê': 'e',
                'á': 'a', 'à': 'a', 'â': 'a',
                'ó': 'o', 'ò': 'o', 'ô': 'o',
                'í': 'i', 'ì': 'i', 'î': 'i',
                'ú': 'u', 'ù': 'u', 'û': 'u'
            }

            for german, english in replacements.items():
                s = s.replace(german, english)

            # Keep only ASCII chars, numbers, and safe special chars
            return "".join(c for c in s if c.isascii() and (c.isalnum() or c in "_-"))

        safe_first_name = sanitize_filename(first_name)
        safe_last_name = sanitize_filename(last_name)
        file_extension = profile_image.filename.split(".")[-1].lower()
        file_path = f"{safe_first_name}_{safe_last_name}.{file_extension}"

        # Read file content as bytes
        file_content = await profile_image.read()

        try:
            # Remove existing file if it exists
            try:
                supabase.storage.from_("profile-images").remove([file_path])
                logger.debug(f"Removed existing file: {file_path}")
            except Exception as e:
                logger.debug(f"No existing file to remove or removal failed: {str(e)}")

            # Upload new file with raw bytes
            result = supabase.storage.from_("profile-images").upload(
                path=file_path,
                file=file_content,
                file_options={
                    "content-type": profile_image.content_type
                }
            )

            logger.debug(f"Upload result: {result}")

            # Get public URL
            image_url = supabase.storage.from_("profile-images").get_public_url(file_path)
            profile_data["profile_image_url"] = image_url

            logger.debug(f"Successfully uploaded image, URL: {image_url}")

            # Create profile using service with language parameter
            profile_create = ProfileCreate(**profile_data)
            return await ProfileService.create_profile(profile_create, language=language)

        except Exception as e:
            logger.error(f"Storage error: {str(e)}")
            logger.error(f"Error details: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Error processing profile image: {str(e)}"
            )

    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)[-1]
        error_info = f"Error in {tb.filename}, line {tb.lineno}: {str(e)}"
        logger.error(f"Validation error: {error_info}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing profile: {error_info}"
        )

@router.get("/{profile_id}")
async def get_profile(profile_id: UUID):
    """Get a profile by ID"""
    try:
        logger.debug(f"Fetching profile with ID: {profile_id}")
        service = ProfileService()
        profile = await service.get_profile(profile_id)

        if not profile:
            logger.debug(f"Profile not found: {profile_id}")
            raise HTTPException(status_code=404, detail="Profile not found")

        return profile
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error fetching profile: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{profile_id}")
async def delete_profile(profile_id: UUID):
    """Delete a profile and all associated data"""
    try:
        logger.debug(f"Deleting profile with ID: {profile_id}")
        service = ProfileService()

        # Delete profile and all associated data
        success = await service.delete_profile(profile_id)

        if not success:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {"message": "Profile and all associated data deleted successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting profile: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rating/{profile_id}", response_model=ProfileRating)
async def get_profile_rating(profile_id: UUID, language: str = Query(default="en")):
    """Get rating statistics for a profile"""
    try:
        service = ProfileService()
        return await service.get_profile_rating(profile_id, language)
    except Exception as e:
        logger.error(f"Error getting profile rating: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get profile rating: {str(e)}"
        )