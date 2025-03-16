# api/v1/scratchpads.py
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, Header, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Dict, Any, Optional
from uuid import UUID
import os
import logging
from datetime import datetime
from dependencies.auth import get_current_user_dependency
from models.scratchpad import ScratchpadFile, ScratchpadFiles, ScratchpadFileResponse
from services.scratchpads import ScratchpadService, INPUT_AGENT_ID
from starlette.requests import Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scratchpads", tags=["scratchpads"])
security = HTTPBearer()

# Get API key from environment
ngina_scratchpad_key = os.getenv("NGINA_SCRATCHPAD_KEY")

async def get_api_key(x_ngina_key: Optional[str] = Header(None)) -> str:
    """Validate the API key for service-to-service communication"""
    if x_ngina_key is None or x_ngina_key != ngina_scratchpad_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return x_ngina_key

# Helper function to convert JSON to files
async def handle_json_as_files(data: Dict[str, Any]) -> List[UploadFile]:
    """Convert JSON data to a file for upload"""
    import json
    from fastapi import UploadFile
    from io import BytesIO

    # This is a simplistic implementation
    # You may need to adapt it based on your UploadFile handling
    json_str = json.dumps(data)
    file_content = BytesIO(json_str.encode())

    # Create an UploadFile object
    upload_file = UploadFile(
        filename="data.json",
        file=file_content
    )

    return [upload_file]

# Endpoint routes
@router.get("/{run_id}", response_model=ScratchpadFiles)
async def get_scratchpad_files(
    run_id: UUID,
    user_id: UUID = Depends(get_current_user_dependency)
):
    """Get all files for a specific run_id, grouped by agent_id (excluding input files)"""
    service = ScratchpadService()
    return await service.get_scratchpad_files(run_id, user_id)

@router.get("/{run_id}/input", response_model=List[ScratchpadFile])
async def get_input_files(
    run_id: UUID,
    user_id: UUID = Depends(get_current_user_dependency)
):
    """Get all input files for a specific run_id"""
    service = ScratchpadService()
    return await service.get_input_files(run_id, user_id)

@router.post("/{user_id}/{run_id}/{agent_id}")
async def upload_files(
    request: Request,
    user_id: UUID,
    run_id: UUID,
    agent_id: UUID,
    current_user: UUID = Depends(get_current_user_dependency),
    x_ngina_key: Optional[str] = Header(None),
    file: UploadFile = File(...)  # Explicitly require a file
):
    """Upload files to the scratchpad"""
    
    # Validate API key
    api_key_missing = x_ngina_key is None or x_ngina_key != ngina_scratchpad_key
       
    # Verify user authentication
    user_jwt_missing = str(current_user) != str(user_id)

    if api_key_missing and user_jwt_missing:
        logger.warning(f"⚠️ Use API key or JWT authentication")
        raise HTTPException(
            status_code=403,
            detail="Unauthenticated: No API key or JWT provided"
        )

    # Process the file directly
    service = ScratchpadService()
    try:
        # Create a list with the single file
        file_list = [file]
        uploaded_files = await service.upload_files(user_id, run_id, agent_id, file_list)
        logger.info(f"✅ Successfully uploaded {len(uploaded_files)} files")
    except Exception as e:
        logger.error(f"❌ Error uploading files: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading files: {str(e)}"
        )

    # Return a different response format for input files
    if str(agent_id) == INPUT_AGENT_ID:
        return {
            "message": f"Successfully uploaded {len(uploaded_files)} input files",
            "run_id": str(run_id),
            "files": uploaded_files
        }
    else:
        return {
            "message": f"Successfully uploaded {len(uploaded_files)} files",
            "run_id": str(run_id),
            "agent_id": str(agent_id),
            "files": [file.filename for file in uploaded_files]
        }

@router.post("/{user_id}/{run_id}/{agent_id}/files")
async def upload_files_auth(
    user_id: UUID,
    run_id: UUID,
    agent_id: UUID,
    current_user: UUID = Depends(get_current_user_dependency),
    file: UploadFile = File(...)  # Explicitly require a file
):
    """Upload files to the scratchpad with user JWT authentication"""
    # Log request information
    logger.info(f"⭐ FILES UPLOAD REQUEST RECEIVED ⭐")
    logger.info(f"Path params: user_id={user_id}, run_id={run_id}, agent_id={agent_id}")
    logger.info(f"Current user: {current_user}")
    logger.info(f"File: {file.filename}, content-type: {file.content_type}")

    # Verify user authentication
    if str(current_user) != str(user_id):
        logger.warning(f"⚠️ User mismatch: current_user={current_user}, user_id={user_id}")
        raise HTTPException(
            status_code=403,
            detail="You can only upload files to your own scratchpad"
        )

    # Process the file
    service = ScratchpadService()
    try:
        # Create a list with the single file
        file_list = [file]
        uploaded_files = await service.upload_files(user_id, run_id, agent_id, file_list)
        logger.info(f"✅ Successfully uploaded {len(uploaded_files)} files")
    except Exception as e:
        logger.error(f"❌ Error uploading files: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading files: {str(e)}"
        )

    # Return a different response format for input files
    if str(agent_id) == INPUT_AGENT_ID:
        return {
            "message": f"Successfully uploaded {len(uploaded_files)} input files",
            "run_id": str(run_id),
            "files": uploaded_files
        }
    else:
        return {
            "message": f"Successfully uploaded {len(uploaded_files)} files",
            "run_id": str(run_id),
            "agent_id": str(agent_id),
            "files": [file.filename for file in uploaded_files]
        }

@router.post("/{user_id}/{run_id}/{agent_id}/json")
async def upload_json(
    user_id: UUID,
    run_id: UUID,
    agent_id: UUID,
    data: Dict[str, Any] = Body(...),  # For JSON data
    x_ngina_key: Optional[str] = Header(None)
):
    """Upload JSON data to the scratchpad

    This endpoint can handle both regular user uploads and system-generated uploads
    """
    # Validate API key
    if x_ngina_key is None or x_ngina_key != ngina_scratchpad_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )

    try:
        service = ScratchpadService()

        # Handle as a system upload of JSON data
        result = await service.upload_json_system(user_id, run_id, agent_id, data)
        return result
       
    except Exception as e:
        logger.error(f"Error uploading data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload data: {str(e)}"
        )

@router.get("/{run_id}/{path:path}", response_model=ScratchpadFileResponse)
async def get_file_by_path(
    run_id: UUID,
    path: str,
    user_id: UUID = Depends(get_current_user_dependency)
):
    """Get file metadata and URL by path"""
    service = ScratchpadService()
    return await service.get_file_by_path(run_id, path, user_id)

@router.delete("/{run_id}")
async def delete_scratchpad(
    run_id: UUID,
    user_id: UUID = Depends(get_current_user_dependency)
):
    """Delete all files for a specific run_id"""
    service = ScratchpadService()
    return await service.delete_scratchpad(run_id, user_id)