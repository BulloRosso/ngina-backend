# api/v1/scratchpads.py
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, Header, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Dict, Any, Optional
from uuid import UUID
import os
import logging
from datetime import datetime, timedelta
from dependencies.auth import get_current_user_dependency
from models.scratchpad import ScratchpadFile, ScratchpadFiles, ScratchpadFileResponse, ScratchpadFileMetadata
from supabase import create_client, Client
import httpx
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scratchpads", tags=["scratchpads"])
security = HTTPBearer()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
ngina_scratchpad_key = os.getenv("NGINA_SCRATCHPAD_KEY")

def get_supabase_client() -> Client:
    """Create and return a Supabase client instance"""
    return create_client(supabase_url, supabase_key)

async def get_api_key(x_ngina_key: Optional[str] = Header(None)) -> str:
    """Validate the API key for service-to-service communication"""
    if x_ngina_key is None or x_ngina_key != ngina_scratchpad_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return x_ngina_key

class ScratchpadService:
    def __init__(self):
        self.supabase = get_supabase_client()
        self.bucket_name = "runtimeresults"

    async def get_scratchpad_files(self, run_id: UUID, user_id: UUID) -> ScratchpadFiles:
        """Get all files for a specific run_id, grouped by agent_id"""
        try:
            # Query the scratchpad_files table for matching run_id and user_id
            result = self.supabase.table("scratchpad_files")\
                .select("*")\
                .eq("run_id", str(run_id))\
                .eq("user_id", str(user_id))\
                .execute()

            if not result.data:
                return ScratchpadFiles()

            # Group files by agent_id
            files_by_agent = {}
            for file_data in result.data:
                agent_id = UUID(file_data.get("agent_id"))
                scratchpad_file = ScratchpadFile.model_validate(file_data)

                if agent_id not in files_by_agent:
                    files_by_agent[agent_id] = []

                files_by_agent[agent_id].append(scratchpad_file)

            return ScratchpadFiles(files=files_by_agent)

        except Exception as e:
            logger.error(f"Error retrieving scratchpad files: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve scratchpad files: {str(e)}"
            )

    async def upload_files(self, user_id: UUID, run_id: UUID, agent_id: UUID, files: List[UploadFile]) -> List[ScratchpadFile]:
        uploaded_files = []

        try:
            for file in files:
                # Construct file path in storage
                file_path = f"{user_id}/{run_id}/{agent_id}/{file.filename}"

                # Read file content
                content = await file.read()

                # Upload file to Supabase storage
                result = self.supabase.storage\
                    .from_(self.bucket_name)\
                    .upload(file_path, content, {"content-type": file.content_type})

                if isinstance(result, dict) and "error" in result:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to upload file {file.filename}: {result['error']}"
                    )

                # Create signed URL (valid for 1 hour)
                signed_url_result = self.supabase.storage\
                    .from_(self.bucket_name)\
                    .create_signed_url(file_path, 3600)

                if isinstance(signed_url_result, dict) and "error" in signed_url_result:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to create signed URL for {file.filename}: {signed_url_result['error']}"
                    )

                # Extract URL correctly based on response structure
                url = None
                if isinstance(signed_url_result, dict) and "signedURL" in signed_url_result:
                    url = signed_url_result["signedURL"]
                else:
                    # Try to find the URL in a different format
                    url = str(signed_url_result)

                # Create metadata record with string UUIDs instead of UUID objects
                metadata = {
                    "user_id": str(user_id),
                    "run_id": str(run_id),
                    "url": url,
                    "created_at": datetime.now().isoformat()
                }

                # Insert record into scratchpad_files table
                file_record = {
                    "user_id": str(user_id),
                    "run_id": str(run_id),
                    "agent_id": str(agent_id),
                    "filename": file.filename,
                    "path": file_path,
                    "metadata": metadata  # Now using the dictionary directly instead of model_dump()
                }

                result = self.supabase.table("scratchpad_files")\
                    .insert(file_record)\
                    .execute()

                if not result.data:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to store metadata for {file.filename}"
                    )

                # Create a ScratchpadFile from the result data
                try:
                    # Convert the metadata back to ScratchpadFileMetadata for the response
                    result_data = result.data[0]
                    metadata_obj = ScratchpadFileMetadata(
                        user_id=user_id,
                        run_id=run_id,
                        url=url,
                        created_at=datetime.fromisoformat(metadata["created_at"]) if isinstance(metadata["created_at"], str) else metadata["created_at"]
                    )

                    # Update the metadata in the result data before validation
                    result_data["metadata"] = metadata_obj.model_dump()

                    # Validate the complete object
                    scratchpad_file = ScratchpadFile.model_validate(result_data)
                    uploaded_files.append(scratchpad_file)
                except Exception as validation_error:
                    logger.error(f"Error validating result data: {str(validation_error)}")
                    # Continue with the next file even if validation fails for this one
                    continue

            return uploaded_files

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading files: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload files: {str(e)}"
            )

    async def upload_files_system(self, run_id: UUID, agent_id: UUID, data: Any) -> Dict[str, Any]:
        """Upload JSON data as a file to the scratchpad as a system operation"""
        try:
            # For system operations, we use a fixed user_id (could be a system user or a special UUID)
            # This is a placeholder - adjust according to your system user ID strategy
            system_user_id = UUID("00000000-0000-0000-0000-000000000000")

            # Generate a filename for the JSON data
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"system_results_{timestamp}.json"

            # Construct file path in storage
            file_path = f"{system_user_id}/{run_id}/{agent_id}/{filename}"

            # Convert data to JSON string
            json_content = json.dumps(data)

            # Upload file to Supabase storage
            result = self.supabase.storage\
                .from_(self.bucket_name)\
                .upload(file_path, json_content, {"content-type": "application/json"})

            if isinstance(result, dict) and "error" in result:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload file: {result['error']}"
                )

            # Create signed URL (valid for 1 hour)
            signed_url_result = self.supabase.storage\
                .from_(self.bucket_name)\
                .create_signed_url(file_path, 3600)

            if isinstance(signed_url_result, dict) and "error" in signed_url_result:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create signed URL: {signed_url_result['error']}"
                )

            # Extract URL correctly based on response structure
            url = None
            if isinstance(signed_url_result, dict) and "signedURL" in signed_url_result:
                url = signed_url_result["signedURL"]
            else:
                # Try to find the URL in a different format
                url = str(signed_url_result)

            # Create metadata record
            metadata = {
                "user_id": str(system_user_id),
                "run_id": str(run_id),
                "url": url,
                "created_at": datetime.now().isoformat()
            }

            # Insert record into scratchpad_files table
            file_record = {
                "user_id": str(system_user_id),
                "run_id": str(run_id),
                "agent_id": str(agent_id),
                "filename": filename,
                "path": file_path,
                "metadata": metadata,
                "system_generated": True  # Flag to indicate this was generated by the system
            }

            result = self.supabase.table("scratchpad_files")\
                .insert(file_record)\
                .execute()

            if not result.data:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to store metadata for system results"
                )

            return {
                "message": "Successfully uploaded system results",
                "run_id": str(run_id),
                "agent_id": str(agent_id),
                "filename": filename,
                "url": url
            }

        except Exception as e:
            logger.error(f"Error uploading system files: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload system files: {str(e)}"
            )

    async def get_file_by_path(self, run_id: UUID, path: str, user_id: UUID) -> ScratchpadFileResponse:
        """Get file metadata and URL by path"""
        try:
            # Extract agent_id and filename from path
            path_parts = path.split('/')
            if len(path_parts) < 2:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid path format. Expected: agent_id/filename"
                )

            agent_id = path_parts[0]
            filename = '/'.join(path_parts[1:])  # In case filename contains slashes

            # Query the database for the file
            result = self.supabase.table("scratchpad_files")\
                .select("*")\
                .eq("run_id", str(run_id))\
                .eq("user_id", str(user_id))\
                .eq("agent_id", agent_id)\
                .eq("filename", filename)\
                .execute()

            if not result.data:
                raise HTTPException(
                    status_code=404,
                    detail=f"File not found: {path}"
                )

            file_data = result.data[0]
            metadata = ScratchpadFileMetadata.model_validate(file_data["metadata"])

            # Check if the URL is still valid (not expired)
            if "signedURL" in metadata.url:
                # Generate a new signed URL if needed
                signed_url_result = self.supabase.storage\
                    .from_(self.bucket_name)\
                    .create_signed_url(file_data["path"], 3600)

                if "error" in signed_url_result:
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Failed to create signed URL: {signed_url_result['error']}"
                    )

                url = signed_url_result["signedURL"]

                # Update the metadata with the new URL
                updated_metadata = metadata.model_dump()
                updated_metadata["url"] = url

                self.supabase.table("scratchpad_files")\
                    .update({"metadata": updated_metadata})\
                    .eq("id", file_data["id"])\
                    .execute()

                metadata.url = url

            return ScratchpadFileResponse(
                metadata=metadata,
                url=metadata.url
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving file: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve file: {str(e)}"
            )

    async def delete_scratchpad(self, run_id: UUID, user_id: UUID) -> Dict[str, Any]:
        """Delete all files for a specific run_id from storage and database"""
        try:
            # First, get all files for this run_id
            result = self.supabase.table("scratchpad_files")\
                .select("*")\
                .eq("run_id", str(run_id))\
                .eq("user_id", str(user_id))\
                .execute()

            if not result.data:
                return {"message": f"No files found for run_id: {run_id}"}

            # Delete files from storage
            file_paths = [file_data["path"] for file_data in result.data]

            for path in file_paths:
                self.supabase.storage\
                    .from_(self.bucket_name)\
                    .remove([path])

            # Delete metadata records
            delete_result = self.supabase.table("scratchpad_files")\
                .delete()\
                .eq("run_id", str(run_id))\
                .eq("user_id", str(user_id))\
                .execute()

            deleted_count = len(delete_result.data) if delete_result.data else 0

            return {
                "message": f"Successfully deleted scratchpad for run_id: {run_id}",
                "deleted_files_count": deleted_count,
                "run_id": str(run_id)
            }

        except Exception as e:
            logger.error(f"Error deleting scratchpad: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete scratchpad: {str(e)}"
            )

    async def upload_json_system(self, user_id: UUID, run_id: UUID, agent_id: UUID, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upload JSON data as a file for system operations"""
        try:
            # Generate a filename for the JSON data
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"system_results_{timestamp}.json"

            # Construct file path in storage
            file_path = f"{user_id}/{run_id}/{agent_id}/{filename}"

            # Convert data to JSON string
            import json
            json_content = json.dumps(data)

            # Upload file to Supabase storage
            result = self.supabase.storage\
                .from_(self.bucket_name)\
                .upload(file_path, json_content, {"content-type": "application/json"})

            if isinstance(result, dict) and "error" in result:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload file: {result['error']}"
                )

            # Create signed URL (valid for 1 hour)
            signed_url_result = self.supabase.storage\
                .from_(self.bucket_name)\
                .create_signed_url(file_path, 3600)

            if isinstance(signed_url_result, dict) and "error" in signed_url_result:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create signed URL: {signed_url_result['error']}"
                )

            # Extract URL correctly based on response structure
            url = None
            if isinstance(signed_url_result, dict) and "signedURL" in signed_url_result:
                url = signed_url_result["signedURL"]
            else:
                # Try to find the URL in a different format
                url = str(signed_url_result)

            # Create metadata record
            metadata = {
                "user_id": str(user_id),
                "run_id": str(run_id),
                "url": url,
                "created_at": datetime.now().isoformat()
            }

            # Insert record into scratchpad_files table
            file_record = {
                "user_id": str(user_id),
                "run_id": str(run_id),
                "agent_id": str(agent_id),
                "filename": filename,
                "path": file_path,
                "metadata": metadata,
                "system_generated": True  # Flag to indicate this was generated by the system
            }

            result = self.supabase.table("scratchpad_files")\
                .insert(file_record)\
                .execute()

            if not result.data:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to store metadata for system results"
                )

            return {
                "message": "Successfully uploaded system results",
                "run_id": str(run_id),
                "agent_id": str(agent_id),
                "filename": filename,
                "url": url
            }

        except Exception as e:
            logger.error(f"Error uploading system JSON: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload system JSON: {str(e)}"
            )

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
    """Get all files for a specific run_id, grouped by agent_id"""
    service = ScratchpadService()
    return await service.get_scratchpad_files(run_id, user_id)

@router.post("/{user_id}/{run_id}/{agent_id}")
async def upload_files(
    user_id: UUID,
    run_id: UUID,
    agent_id: UUID,
    files: List[UploadFile] = File(...),
    api_key: str = Depends(get_api_key)
):
    """Upload files to the scratchpad"""
    service = ScratchpadService()
    uploaded_files = await service.upload_files(user_id, run_id, agent_id, files)
    return {
        "message": f"Successfully uploaded {len(uploaded_files)} files",
        "run_id": str(run_id),
        "agent_id": str(agent_id),
        "files": [file.filename for file in uploaded_files]
    }

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

@router.post("/{user_id}/{run_id}/{agent_id}")
async def upload_files(
    user_id: UUID,
    run_id: UUID,
    agent_id: UUID,
    data: Dict[str, Any] = Body(...),  # For JSON data
    x_ngina_key: Optional[str] = Header(None)
):
    """Upload JSON data to the scratchpad

    This endpoint can handle both regular user uploads and system-generated uploads
    with the system user ID (00000000-0000-0000-0000-000000000000)
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
            # This assumes there's another method for handling files
            # If you're only handling JSON data, you can remove this branch
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