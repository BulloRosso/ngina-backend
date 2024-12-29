# services/memory.py
from typing import Optional, List
from uuid import UUID
from models.memory import MemoryCreate
from supabase import create_client, Client
import os
import asyncio
from datetime import datetime
import logging
import traceback
import io
from PIL import Image
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MemoryService:
    table_name = "memories"
    storage_bucket = "memory-media"
    
    def __init__(self):
        logger.debug("Initializing MemoryService")
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        
    @classmethod
    async def delete_memory(cls, memory_id: UUID) -> bool:
        """Delete a memory by ID"""
        try:
            logger.debug(f"Attempting to delete memory with ID: {memory_id}")
            instance = cls.get_instance()

            # First, get the profile_id from the memory
            memory_result = instance.supabase.table(cls.table_name).select(
                "profile_id"
            ).eq(
                "id", str(memory_id)
            ).execute()

            if not memory_result.data:
                logger.warning(f"No memory found with ID {memory_id} during profile_id lookup for delete")
                return False

            profile_id = memory_result.data[0].get('profile_id')
            if not profile_id:
                logger.warning(f"Memory {memory_id} has no profile_id")
                return False
            
            # Delete the memory from Supabase
            result = instance.supabase.table(cls.table_name).delete().eq(
                "id", str(memory_id)
            ).execute()

            logger.debug(f"Delete response: {result}")

            # Check if deletion was successful
            if not result.data:
                logger.warning(f"No memory found with ID {memory_id}")
                return False

            # Import KnowledgeManagement here to avoid circular import
            from services.knowledgemanagement import KnowledgeManagement
            
            # Delete the memory from neo4j 
            km = KnowledgeManagement()
            asyncio.create_task(km.delete_memory(str(profile_id), str(memory_id)))
            
            return True

        except Exception as e:
            logger.error(f"Error deleting memory: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Failed to delete memory: {str(e)}")

    @classmethod
    async def update_memory(cls, memory_id: UUID, memory_data: dict) -> bool:
        """Update a memory by ID"""
        try:
            logger.debug(f"Attempting to update memory with ID: {memory_id}")
            logger.debug(f"Update data: {memory_data}")

            instance = cls.get_instance()
           
            
            # Handle time_period field name conversion
            if "time_period" in memory_data:
                time_period = memory_data["time_period"]
                # Ensure it's in ISO format if it's not already
                if isinstance(time_period, datetime):
                    time_period = time_period.isoformat()
                memory_data["time_period"] = time_period

            update_data = {}
            
            # Copy existing fields
            for field in ['category', 'description', 'time_period', 'location', 
                         'people', 'emotions', 'image_urls', 'audio_url']:
                if field in memory_data:
                    update_data[field] = memory_data[field]
                    
            # Add new fields if they exist in the update data
            if 'caption' in memory_data:
                update_data['caption'] = memory_data['caption']
            if 'original_description' in memory_data:
                update_data['original_description'] = memory_data['original_description']
                
            # Add updated_at timestamp
            update_data['updated_at'] = datetime.utcnow().isoformat()

            # Update the memory in Supabase
            result = instance.supabase.table(cls.table_name)\
                .update(update_data)\
                .eq("id", str(memory_id))\
                .execute()

            logger.debug(f"Update response: {result}")

            # Check if update was successful
            if not result.data:
                logger.warning(f"No memory found with ID {memory_id}")
                return False

            return result.data[0]

        except Exception as e:
            logger.error(f"Error updating memory: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Failed to update memory: {str(e)}")
            
    @staticmethod
    def get_instance():
        if not hasattr(MemoryService, "_instance"):
            MemoryService._instance = MemoryService()
        return MemoryService._instance

    @classmethod
    async def verify_session(cls, session_id: UUID, profile_id: UUID) -> bool:
        """Verify that the session exists and belongs to the profile"""
        try:
            logger.debug(f"Verifying session for profile_id={profile_id}, session_id={session_id}")
            instance = cls.get_instance()
            result = instance.supabase.table("interview_sessions").select("*").eq(
                "id", str(session_id)
            ).eq(
                "profile_id", str(profile_id)
            ).execute()

            session_exists = len(result.data) > 0
            logger.debug(f"Session verification result: {session_exists}")
            return session_exists
        except Exception as e:
            logger.error(f"Error verifying session: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    @classmethod
    async def create_memory(cls, memory: MemoryCreate, profile_id: UUID, session_id: UUID):
        """Create a new memory"""
        try:
            logger.info(f"Creating memory for profile_id={profile_id}, session_id={session_id}")
            logger.info(f"Memory data: {memory.dict()}")

            instance = cls.get_instance()
            now = datetime.utcnow().isoformat()

            # Log the memory object to see what we're working with
            logger.info(f"Memory object: {memory}")

            # Create the data dictionary with full error handling
            try:
                data = {
                    "profile_id": str(profile_id),
                    "session_id": str(session_id),
                    "category": str(memory.category),
                    "description": str(memory.description),
                    "caption": memory.caption,
                    "original_description": memory.original_description,
                    "time_period": str(memory.time_period),
                    "emotions": [],  # Start with empty arrays if these are causing issues
                    "people": [],
                    "image_urls": [],
                    "created_at": now,
                    "updated_at": now
                }

                # Add optional fields with validation
                if hasattr(memory, 'location') and memory.location:
                    data["location"] = memory.location.dict() if hasattr(memory.location, 'dict') else None

                if hasattr(memory, 'emotions') and memory.emotions:
                    data["emotions"] = [emotion.dict() for emotion in memory.emotions] if all(hasattr(e, 'dict') for e in memory.emotions) else []

                if hasattr(memory, 'people') and memory.people:
                    data["people"] = [person.dict() for person in memory.people] if all(hasattr(p, 'dict') for p in memory.people) else []

                if hasattr(memory, 'image_urls') and memory.image_urls:
                    data["image_urls"] = memory.image_urls

                if hasattr(memory, 'audio_url') and memory.audio_url:
                    data["audio_url"] = memory.audio_url

                logger.info(f"Prepared data for insert: {data}")
            except Exception as e:
                logger.error(f"Error preparing memory data: {str(e)}")
                logger.error(traceback.format_exc())
                raise Exception(f"Error preparing memory data: {str(e)}")

            # Insert into database with error logging
            try:
                response = instance.supabase.table(cls.table_name).insert(data).execute()

                if not response.data:
                    raise Exception("No data returned from memory creation")
                    
                inserted_row = response.data[0]  # Assuming only one row is inserted
                auto_generated_id = inserted_row.get('id')

                return auto_generated_id
                
            except Exception as e:
                logger.error(f"Error inserting into database: {str(e)}")
                logger.error(traceback.format_exc())
                raise

        except Exception as e:
            logger.error(f"Error in create_memory: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Failed to create memory: {str(e)}")

    @classmethod
    async def delete_media_from_memory(cls, memory_id: UUID, filename: str) -> bool:
        """Delete a media file from storage and update the memory record"""
        try:
            logger.debug(f"Deleting media {filename} from memory {memory_id}")
            instance = cls.get_instance()

            # First, get the current memory record to get the image URLs
            memory = instance.supabase.table(cls.table_name)\
                .select("image_urls")\
                .eq("id", str(memory_id))\
                .execute()

            if not memory.data:
                raise Exception("Memory not found")

            # Get current image URLs
            current_urls = memory.data[0].get('image_urls', [])

            # Generate the storage URL that matches our stored URL pattern
            storage_url = instance.supabase.storage\
                .from_(cls.storage_bucket)\
                .get_public_url(f"{memory_id}/{filename}")

            # Find and remove the URL from the list
            updated_urls = [url for url in current_urls if url != storage_url]

            if len(updated_urls) == len(current_urls):
                logger.warning(f"URL not found in memory record: {storage_url}")

            # Delete from storage
            try:
                delete_result = instance.supabase.storage\
                    .from_(cls.storage_bucket)\
                    .remove([f"{memory_id}/{filename}"])

                logger.debug(f"Storage delete result: {delete_result}")
            except Exception as e:
                logger.error(f"Error deleting from storage: {str(e)}")
                # Continue anyway to update the memory record
                pass

            # Update the memory record with the new URL list
            update_result = instance.supabase.table(cls.table_name)\
                .update({"image_urls": updated_urls})\
                .eq("id", str(memory_id))\
                .execute()

            logger.debug(f"Memory update result: {update_result}")

            return True

        except Exception as e:
            logger.error(f"Error deleting media from memory: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Failed to delete media: {str(e)}")

    @classmethod
    async def get_memories_for_profile(cls, profile_id: str):
        """Get all memories for a profile, ordered by time_period"""
        try:
            logger.debug(f"Fetching memories for profile: {profile_id}")
            instance = cls.get_instance()

            result = instance.supabase.table(cls.table_name)\
                .select("*")\
                .eq("profile_id", str(profile_id))\
                .order("time_period")\
                .execute()

            if not result.data:
                logger.info(f"No memories found for profile {profile_id}")
                return []

            return result.data

        except Exception as e:
            logger.error(f"Error fetching memories for profile {profile_id}: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Failed to fetch memories: {str(e)}")
    
    @classmethod
    async def add_media_to_memory(cls, memory_id: UUID, files: List[bytes], content_types: List[str]) -> dict:
        """Add media files to a memory and return the URLs"""
        try:
            logger.debug(f"Adding media to memory {memory_id}")
            instance = cls.get_instance()
    
            # First get the memory to verify it exists and get profile_id
            memory = instance.supabase.table(cls.table_name)\
                .select("*")\
                .eq("id", str(memory_id))\
                .execute()
    
            if not memory.data:
                raise Exception("Memory not found")
    
            profile_id = memory.data[0].get('profile_id')
    
            # Get user_id from profiles table
            profile = instance.supabase.table("profiles")\
                .select("user_id")\
                .eq("id", profile_id)\
                .execute()
    
            if not profile.data:
                raise Exception("Profile not found")
    
            user_id = profile.data[0].get('user_id')
            current_urls = memory.data[0].get('image_urls', [])
            new_urls = []
    
            for idx, (file_content, content_type) in enumerate(zip(files, content_types)):
                try:
                    # Generate unique filename including user_id in path
                    file_ext = "jpg" if "jpeg" in content_type.lower() else "png"
                    filename = f"{user_id}/{memory_id}/{uuid.uuid4()}.{file_ext}"
    
                    # Upload to Supabase Storage
                    result = instance.supabase.storage\
                        .from_(cls.storage_bucket)\
                        .upload(
                            path=filename,
                            file=file_content,
                            file_options={"content-type": content_type}
                        )
    
                    if hasattr(result, 'error') and result.error:
                        raise Exception(f"Upload error: {result.error}")
    
                    # Get public URL with signed URL
                    signed_url = instance.supabase.storage\
                        .from_(cls.storage_bucket)\
                        .create_signed_url(
                            path=filename,
                            expires_in=31536000  # 1 year in seconds
                        )
    
                    if 'signedURL' in signed_url:
                        new_urls.append(signed_url['signedURL'])
                    else:
                        public_url = instance.supabase.storage\
                            .from_(cls.storage_bucket)\
                            .get_public_url(filename)
                        new_urls.append(public_url)
    
                except Exception as e:
                    logger.error(f"Error uploading file {idx}: {str(e)}")
                    continue
    
            # Update memory with new URLs
            updated_urls = current_urls + new_urls
            update_result = instance.supabase.table(cls.table_name)\
                .update({"image_urls": updated_urls})\
                .eq("id", str(memory_id))\
                .execute()
    
            return {
                "message": "Media added successfully",
                "urls": new_urls,
                "total_urls": len(updated_urls)
            }
    
        except Exception as e:
            logger.error(f"Error adding media: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Failed to add media: {str(e)}")