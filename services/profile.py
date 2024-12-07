from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, UUID4
from supabase import create_client, Client
import os


# Environment Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# Pydantic Models
class ProfileBase(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    place_of_birth: str
    gender: str
    children: Optional[List[str]] = Field(default_factory=list)
    spoken_languages: Optional[List[str]] = Field(default_factory=list)
    profile_image_url: Optional[str] = None


class ProfileCreate(ProfileBase):
    pass


class Profile(ProfileBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


# Service Class
class ProfileService:
    table_name = "profiles"

    @classmethod  # Changed from @staticmethod to @classmethod since we need cls
    async def get_all_profiles(cls) -> List[Profile]:
        """Get all profiles"""
        try:
            result = supabase.table(cls.table_name).select("*").order(
                'updated_at', desc=True
            ).execute()

            return [
                Profile(
                    **{
                        **profile,
                        'date_of_birth': datetime.fromisoformat(profile['date_of_birth']).date(),
                        'created_at': datetime.fromisoformat(profile['created_at']),
                        'updated_at': datetime.fromisoformat(profile['updated_at'])
                    }
                )
                for profile in result.data
            ]
        except Exception as e:
            raise Exception(f"Failed to fetch profiles: {str(e)}")
    
    @staticmethod
    async def create_profile(profile_data: ProfileCreate) -> Profile:
        """
        Creates a new profile in the Supabase table.
        """
        try:
            # Convert profile data to dict
            data = {
                "first_name": profile_data.first_name,
                "last_name": profile_data.last_name,
                "date_of_birth": profile_data.date_of_birth.isoformat(),
                "place_of_birth": profile_data.place_of_birth,
                "gender": profile_data.gender,
                "children": profile_data.children,
                "spoken_languages": profile_data.spoken_languages,
                "profile_image_url": profile_data.profile_image_url
            }

            # Insert data into Supabase
            response = supabase.table(ProfileService.table_name).insert(data).execute()
          
            if hasattr(response, 'error') and response.error:
                raise Exception(f"Supabase error: {response.error}")

            result_data = response.data[0] if response.data else None
            if not result_data:
                raise Exception("No data returned from Supabase")

            return Profile(**result_data)
        except Exception as e:
            raise Exception(f"Failed to create profile: {str(e)}")

    @staticmethod
    async def get_profile(profile_id: UUID4) -> Optional[Profile]:
        """
        Retrieves a profile by ID.
        """
        try:
            # Fetch the profile from Supabase
            response = supabase.table(ProfileService.table_name).select("*").eq("id", str(profile_id)).execute()

            # Check for errors
            if response.get("error"):
                raise Exception(f"Supabase error: {response['error']['message']}")

            if response["data"]:
                profile = Profile(**response["data"][0])
                return profile
            return None
        except Exception as e:
            raise Exception(f"Failed to retrieve profile: {str(e)}")

    @staticmethod
    async def update_profile(profile_id: UUID4, profile_data: ProfileCreate) -> Profile:
        """
        Updates an existing profile by ID.
        """
        try:
            # Update data in Supabase
            response = supabase.table(ProfileService.table_name).update(profile_data.dict()).eq("id", str(profile_id)).execute()

            # Check for errors
            if response.get("error"):
                raise Exception(f"Supabase error: {response['error']['message']}")

            if response["data"]:
                profile = Profile(**response["data"][0])
                return profile
            raise Exception("Profile not found")
        except Exception as e:
            raise Exception(f"Failed to update profile: {str(e)}")

    @staticmethod
    async def delete_profile(profile_id: UUID4) -> bool:
        """
        Deletes a profile by ID.
        """
        try:
            # Delete the profile from Supabase
            response = supabase.table(ProfileService.table_name).delete().eq("id", str(profile_id)).execute()

            # Check for errors
            if response.get("error"):
                raise Exception(f"Supabase error: {response['error']['message']}")

            # Return True if deletion was successful
            return response["data"] is not None
        except Exception as e:
            raise Exception(f"Failed to delete profile: {str(e)}")
