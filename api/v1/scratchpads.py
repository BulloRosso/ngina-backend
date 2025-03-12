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
        file=file_content,
        content_type="application/json"
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
    current_user: UUID = Depends(get_current_user_dependency)
):
    """Upload files to the scratchpad"""
    # Super detailed logging
    logger.info(f"⭐ UPLOAD REQUEST RECEIVED ⭐")
    logger.info(f"URL: {request.url}")
    logger.info(f"Method: {request.method}")
    logger.info(f"Path params: user_id={user_id}, run_id={run_id}, agent_id={agent_id}")
    logger.info(f"Current user: {current_user}")

    # Log request headers
    logger.info(f"Request headers:")
    for header_name, header_value in request.headers.items():
        logger.info(f"  {header_name}: {header_value}")

    # Check content type
    content_type = request.headers.get("content-type", "")
    logger.info(f"Content-Type: {content_type}")

    # Verify user authentication
    if str(current_user) != str(user_id):
        logger.warning(f"⚠️ User mismatch: current_user={current_user}, user_id={user_id}")
        raise HTTPException(
            status_code=403,
            detail="You can only upload files to your own scratchpad"
        )

    # Get the raw body for debugging if there's an issue
    try:
        body = await request.body()
        logger.info(f"Request body size: {len(body)} bytes")
        # If small enough, log part of it for debugging
        if len(body) < 1000:
            logger.info(f"Request body preview: {body[:100]}")
    except Exception as e:
        logger.error(f"Failed to read request body: {str(e)}")

    # Try to process the form data manually
    try:
        # Get the form data
        form = await request.form()
        logger.info(f"Form fields: {[key for key in form.keys()]}")

        file_list = []
        # Find any file fields and add them to the list
        for field_name, field_value in form.items():
            if isinstance(field_value, UploadFile):
                logger.info(f"💾 Found file in form field '{field_name}': {field_value.filename}")
                # Log file details
                logger.info(f"  Filename: {field_value.filename}")
                logger.info(f"  Content type: {field_value.content_type}")
                # Try to get file size
                try:
                    size = 0
                    chunk = await field_value.read(8192)
                    while chunk:
                        size += len(chunk)
                        chunk = await field_value.read(8192)
                    # Reset file position for later reading
                    await field_value.seek(0)
                    logger.info(f"  File size: {size} bytes")
                except Exception as e:
                    logger.error(f"  Error getting file size: {str(e)}")

                file_list.append(field_value)
            else:
                logger.info(f"Form field '{field_name}': {field_value}")
    except Exception as e:
        logger.error(f"❌ Error processing form data: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process form data: {str(e)}"
        )

    # Ensure we have at least one file
    if not file_list:
        logger.warning("❌ No files found in the request")
        raise HTTPException(
            status_code=400,
            detail="No files provided for upload"
        )

    logger.info(f"✅ Found {len(file_list)} files to upload")

    # Process the files
    service = ScratchpadService()
    try:
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

        # Check if this is a system user call
        system_user_id = UUID("00000000-0000-0000-0000-000000000000")
        if user_id == system_user_id:
            # Handle as a system upload of JSON data
            result = await service.upload_json_system(user_id, run_id, agent_id, data)
            return result
        else:
            # For regular user uploads
            files = await handle_json_as_files(data)  # Convert JSON to a file object
            uploaded_files = await service.upload_files(user_id, run_id, agent_id, files)
            return {
                "message": f"Successfully uploaded {len(uploaded_files)} files",
                "run_id": str(run_id),
                "agent_id": str(agent_id),
                "files": [file.filename for file in uploaded_files]
            }
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