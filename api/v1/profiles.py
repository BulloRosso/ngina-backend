# api/v1/profiles.py
from fastapi import APIRouter, HTTPException, File, Form, Request, UploadFile
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
import logging

logger = logging.getLogger(__name__)

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
            
@router.post("")
async def create_profile(
  profile_image: UploadFile = File(...),
  profile: str = Form(...)
):
  try:
      profile_data = json.loads(profile)
      # print("Profile data before creation:", profile_data)  # Debug print
      first_name = profile_data.get("first_name")
      last_name = profile_data.get("last_name")
      profile_data["date_of_birth"] = datetime.strptime(profile_data["date_of_birth"], "%Y-%m-%d").date()

      if not first_name or not last_name:
          raise ValueError("Both first_name and last_name are required.")

      file_path = f"profile_images/{first_name}_{last_name}.jpg"
      file_content = await profile_image.read()
      
      try:
          supabase.storage.from_("profile-images").remove([file_path])
      except:
          pass

      result = supabase.storage.from_("profile-images").upload(
          path=file_path,
          file=file_content,
          file_options={"content-type": profile_image.content_type}
      )

      image_url = supabase.storage.from_("profile-images").get_public_url(file_path)
      profile_data["profile_image_url"] = image_url

      profile_create = ProfileCreate(**profile_data)
      return await ProfileService.create_profile(profile_create)

  except Exception as e:
      tb = traceback.extract_tb(e.__traceback__)[-1]
      error_info = f"Error in {tb.filename}, line {tb.lineno}: {str(e)}"
      print(f"Validation error: {error_info}")
      raise HTTPException(
          status_code=500, 
          detail=f"Error processing profile: {error_info}"
      )

@router.get("/{profile_id}")
async def get_profile(profile_id: UUID):
    """Get a profile by ID"""
    try:
        logger.debug(f"Fetching profile with ID: {profile_id}")
        service = ProfileService()  # Create instance
        profile = await service.get_profile(profile_id)  # Call instance method

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

