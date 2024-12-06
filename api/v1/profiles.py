# api/v1/profiles.py
from fastapi import APIRouter, HTTPException, File, Form, Request, UploadFile
from typing import Optional
from uuid import UUID
import json
import os
from models.profile import Profile, ProfileCreate
from supabase import create_client

router = APIRouter(prefix="/profiles", tags=["profiles"])

# Initialize Supabase client
supabase = create_client(
    supabase_url = os.getenv("SUPABASE_URL"),
    supabase_key = os.getenv("SUPABASE_KEY")
)

@router.post("")
async def create_profile(
   profile_image: UploadFile = File(...),
   profile: str = Form(...)
):
   try:
       profile_data = json.loads(profile)
       first_name = profile_data.get("first_name")
       last_name = profile_data.get("last_name")

       if not first_name or not last_name:
           raise ValueError("Both first_name and last_name are required.")
           
       # Upload profile image to Supabase storage
       
       # Construct file path for the image
       file_path = f"profile_images/{first_name}_{last_name}.jpg"
       result = supabase.storage.from_("profile-images").upload(
           file_path,
           profile_image.file.read(),
       )

       # Get public URL for the image
       image_url = supabase.storage.from_("profile-images").get_public_url(file_path)

       # Create profile with image URL
       profile_data["profile_image_url"] = image_url
       return await Profile.create(profile_data)
   except Exception as e:
       print(f"Validation error: {str(e)}")  # Debug print
       raise HTTPException(
           status_code=500, 
           detail=f"Error processing profile: {str(e)}"
       )

@router.get("/{profile_id}")
async def get_profile(profile_id: UUID):
   try:
       return await Profile.get(profile_id)
   except Exception as e:
       raise HTTPException(status_code=404, detail=str(e))

@router.put("/{profile_id}")
async def update_profile(profile_id: UUID, profile: ProfileCreate):
   try:
       return await Profile.update(profile_id, profile)
   except Exception as e:
       raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{profile_id}")
async def delete_profile(profile_id: UUID):
   try:
       return await Profile.delete(profile_id)
   except Exception as e:
       raise HTTPException(status_code=404, detail=str(e))