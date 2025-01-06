# api/v1/memories.py
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Depends
from typing import List
from uuid import UUID
from models.memory import Memory, MemoryCreate, MemoryUpdate
from services.memory import MemoryService
import logging
import traceback
from pydantic import BaseModel
from datetime import datetime
import io
from dependencies.auth import get_current_user

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memories"])

@router.get("/memory/{memory_id}")
async def get_memory_by_id(
   memory_id: UUID,
   user_id: UUID = Depends(get_current_user)
) -> Memory:
   try:
       memory_service = MemoryService.get_instance()

       # Get memory with profile_id
       result = memory_service.supabase.table("memories").select("*,profiles!inner(user_id)").eq(
           "id", str(memory_id)
       ).single().execute()

       if not result.data:
           raise HTTPException(status_code=404, detail="Memory not found")

       # Check if memory belongs to user
       if str(user_id) != result.data["profiles"]["user_id"]:
           raise HTTPException(status_code=403, detail="Forbidden")

       # Clean category format
       if isinstance(result.data.get('category'), str):
           result.data['category'] = result.data['category'].replace('Category.', '')

       return Memory(**result.data)

   except Exception as e:
       logger.error(f"Error fetching memory: {str(e)}")
       raise HTTPException(status_code=500, detail=str(e))
       
@router.put("/{memory_id}")
async def update_memory(memory_id: UUID, memory: MemoryUpdate):
    """Update a memory by ID"""
    try:
        # Add explicit print for immediate visibility
        print(f"\n=== Update Memory Request ===")
        print(f"Memory ID: {memory_id}")
        print(f"Update Data: {memory.dict(exclude_unset=True)}")

        logger.info(f"=== Update Memory Request ===")
        logger.info(f"Memory ID: {memory_id}")
        logger.info(f"Raw update data: {memory}")

        # Only include fields that were actually provided in the update
        update_data = memory.dict(exclude_unset=True)
        logger.info(f"Processed update data: {update_data}")

        if 'time_period' in update_data:
            print(f"Time period in update: {update_data['time_period']}")
            logger.info(f"Time period in update: {update_data['time_period']}")

        result = await MemoryService.update_memory(memory_id, update_data)
        print(f"Update result: {result}")
        logger.info(f"Update result: {result}")

        return result

    except Exception as e:
        logger.error(f"Error updating memory: {str(e)}")
        print(f"Error updating memory: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update memory: {str(e)}"
        )

@router.get("/{profile_id}")
async def get_memories_by_profile(profile_id: UUID) -> List[Memory]:
    """Get all memories for a specific profile"""
    try:
        logger.debug(f"Fetching memories for profile_id={profile_id}")

        memory_service = MemoryService.get_instance()
        result = memory_service.supabase.table("memories").select("*").eq(
            "profile_id", str(profile_id)
        ).order('created_at', desc=True).execute()

        if not result.data:
            return []

        # Convert string category to enum value
        memories = []
        for memory_data in result.data:
            # Remove 'Category.' prefix if it exists
            if isinstance(memory_data.get('category'), str):
                memory_data['category'] = memory_data['category'].replace('Category.', '')
            try:
                memories.append(Memory(**memory_data))
            except Exception as e:
                logger.error(f"Error converting memory data: {str(e)}")
                logger.error(f"Problematic memory data: {memory_data}")
                continue

        return memories

    except Exception as e:
        logger.error(f"Error fetching memories: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch memories: {str(e)}"
        )
        
@router.post("")
async def create_memory(
    request: Request,
    memory: MemoryCreate,
    profile_id: UUID,
    session_id: UUID
):
    try:
        logger.debug(f"Received create memory request for profile_id={profile_id}, session_id={session_id}")
        logger.debug(f"Memory data: {memory.dict()}")

        # Verify the session exists first
        session_exists = await MemoryService.verify_session(session_id, profile_id)
        if not session_exists:
            logger.warning(f"Session not found: profile_id={profile_id}, session_id={session_id}")
            raise HTTPException(
                status_code=404,
                detail="Interview session not found or doesn't belong to this profile"
            )

        # Log the request body for debugging
        body = await request.json()
        logger.debug(f"Request body: {body}")

        result = await MemoryService.create_memory(memory, profile_id, session_id)
        logger.debug(f"Memory created successfully: {result}")
        return result
    except HTTPException as he:
        logger.error(f"HTTP Exception: {str(he)}")
        raise
    except Exception as e:
        logger.error(f"Error creating memory: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error creating memory: {str(e)}"
        )

@router.delete("/{memory_id}")
async def delete_memory(memory_id: UUID):
    """Delete a memory by ID"""
    try:
        logger.debug(f"Received delete request for memory_id={memory_id}")

        deleted = await MemoryService.delete_memory(memory_id)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Memory not found"
            )

        return {"status": "success", "message": "Memory deleted successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting memory: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete memory: {str(e)}"
        )

@router.delete("/{memory_id}/media/{filename}")
async def delete_media_from_memory(memory_id: UUID, filename: str):
    """Delete a media file from a memory"""
    try:
        logger.debug(f"Deleting media {filename} from memory {memory_id}")

        result = await MemoryService.delete_media_from_memory(memory_id, filename)

        return {"success": True, "message": "Media deleted successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting media: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete media: {str(e)}"
        )
        
@router.post("/{memory_id}/media")
async def add_media_to_memory(
    memory_id: UUID,
    files: List[UploadFile] = File(...),
):
    """Add media files to a memory"""
    try:
        logger.debug(f"Received media upload request for memory_id={memory_id}")
        logger.debug(f"Number of files: {len(files)}")

        # Read and validate each file
        file_contents = []
        content_types = []

        for file in files:
            content_type = file.content_type
            if not content_type.startswith('image/'):
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} is not an image"
                )

            content = await file.read()
            file_contents.append(content)
            content_types.append(content_type)

        # Process the files
        result = await MemoryService.add_media_to_memory(
            memory_id=memory_id,
            files=file_contents,
            content_types=content_types
        )

        return result

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error adding media: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add media: {str(e)}"
        )