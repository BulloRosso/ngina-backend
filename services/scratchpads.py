# services/scratchpads.py
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID
from fastapi import HTTPException, UploadFile
from supabase import create_client, Client
from urllib.parse import urlparse, parse_qs
from models.scratchpad import ScratchpadFile, ScratchpadFiles, ScratchpadFileResponse, ScratchpadFileMetadata

logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

# Define a special agent ID for input files (using a specific UUID)
INPUT_AGENT_ID = "00000000-0000-0000-0000-000000000001"

def get_supabase_client() -> Client:
    """Create and return a Supabase client instance"""
    return create_client(supabase_url, supabase_key)

def is_url_expired(url: str, threshold_minutes: int = 5) -> bool:
    """
    Check if a Supabase Storage URL's SAS token is expired or about to expire

    Args:
        url: The signed URL to check
        threshold_minutes: Number of minutes before expiration to consider a URL as "expired"

    Returns:
        bool: True if the URL is expired or will expire soon, False otherwise
    """
    try:
        # Parse the URL
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        # Extract the expiry parameter (usually 'se' in SAS tokens)
        if 'se' not in query_params:
            return True  # No expiry parameter found, consider expired

        # Parse the expiry timestamp
        expiry_timestamp = int(query_params['se'][0])
        expiry_time = datetime.fromtimestamp(expiry_timestamp)

        # Calculate the threshold time
        current_time = datetime.now()
        threshold_time = current_time + timedelta(minutes=threshold_minutes)

        # Check if the URL will expire within the threshold
        return expiry_time <= threshold_time

    except Exception as e:
        logger.error(f"Error checking URL expiration: {str(e)}")
        return True  # Consider expired on error

class ScratchpadService:
    def __init__(self):
        self.supabase = get_supabase_client()
        self.bucket_name = "runtimeresults"

    async def get_scratchpad_files(self, run_id: UUID, user_id: UUID) -> ScratchpadFiles:
        """Get all files for a specific run_id, grouped by agent_id"""
        try:
            # Query the scratchpad_files table for matching run_id and user_id
            # Exclude files from the special input agent (now using a UUID)
            result = self.supabase.table("scratchpad_files")\
                .select("*")\
                .eq("run_id", str(run_id))\
                .eq("user_id", str(user_id))\
                .neq("agent_id", INPUT_AGENT_ID)\
                .execute()

            if not result.data:
                return ScratchpadFiles()

            # Group files by agent_id
            files_by_agent = {}
            for file_data in result.data:
                agent_id = UUID(file_data.get("agent_id"))

                # Get the file path for creating a fresh signed URL
                file_path = file_data.get("path")

                # Check if the URL is expired or will expire soon
                current_url = file_data.get("metadata", {}).get("url", "")
                fresh_url = current_url

                # Refresh the URL if needed
                try:
                    if is_url_expired(current_url):
                        # Create a new signed URL (valid for 1 hour)
                        signed_url_result = self.supabase.storage\
                            .from_(self.bucket_name)\
                            .create_signed_url(file_path, 3600)

                        if isinstance(signed_url_result, dict) and "signedURL" in signed_url_result:
                            fresh_url = signed_url_result["signedURL"]
                        else:
                            fresh_url = str(signed_url_result)

                        # Update the URL in the metadata
                        metadata = file_data.get("metadata", {})
                        metadata["url"] = fresh_url
                        file_data["metadata"] = metadata

                    # Create the ScratchpadFile with the updated metadata
                    scratchpad_file = ScratchpadFile.model_validate(file_data)

                    if agent_id not in files_by_agent:
                        files_by_agent[agent_id] = []

                    files_by_agent[agent_id].append(scratchpad_file)

                except Exception as file_error:
                    # Log the error but continue processing other files
                    logger.warning(f"Error refreshing URL for file {file_path}: {str(file_error)}")
                    # Skip this file and continue with others
                    # Optionally, you could add the file with the original URL instead

                    # If you want to include the file with its original URL (might still be broken):
                    try:
                        scratchpad_file = ScratchpadFile.model_validate(file_data)
                        if agent_id not in files_by_agent:
                            files_by_agent[agent_id] = []
                        files_by_agent[agent_id].append(scratchpad_file)
                    except Exception:
                        # If even that fails, just skip this file entirely
                        pass

            return ScratchpadFiles(files=files_by_agent)

        except Exception as e:
            logger.error(f"Error retrieving scratchpad files: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve scratchpad files: {str(e)}"
            )

    async def get_input_files(self, run_id: UUID, user_id: UUID) -> List[ScratchpadFile]:
        """Get all input files for a specific run_id"""
        try:
            # Query the scratchpad_files table for matching run_id, user_id, and input agent_id
            # Now using a specific UUID for the input agent
            result = self.supabase.table("scratchpad_files")\
                .select("*")\
                .eq("run_id", str(run_id))\
                .eq("user_id", str(user_id))\
                .eq("agent_id", INPUT_AGENT_ID)\
                .execute()

            if not result.data:
                return []

            input_files = []
            for file_data in result.data:
                # Get the file path for creating a fresh signed URL
                file_path = file_data.get("path")

                # Check if the URL is expired or will expire soon
                current_url = file_data.get("metadata", {}).get("url", "")
                fresh_url = current_url

                # Refresh the URL if needed
                try:
                    if is_url_expired(current_url):
                        # Create a new signed URL (valid for 1 hour)
                        signed_url_result = self.supabase.storage\
                            .from_(self.bucket_name)\
                            .create_signed_url(file_path, 3600)

                        if isinstance(signed_url_result, dict) and "signedURL" in signed_url_result:
                            fresh_url = signed_url_result["signedURL"]
                        else:
                            fresh_url = str(signed_url_result)

                        # Update the URL in the metadata
                        metadata = file_data.get("metadata", {})
                        metadata["url"] = fresh_url
                        file_data["metadata"] = metadata

                    # Create the ScratchpadFile with the updated metadata
                    scratchpad_file = ScratchpadFile.model_validate(file_data)
                    input_files.append(scratchpad_file)

                except Exception as file_error:
                    # Log the error but continue processing other files
                    logger.warning(f"Error refreshing URL for input file {file_path}: {str(file_error)}")
                    continue

            return input_files

        except Exception as e:
            logger.error(f"Error retrieving input files: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve input files: {str(e)}"
            )

    async def upload_files(self, user_id: UUID, run_id: UUID, agent_id: UUID, files: List[UploadFile]) -> List[ScratchpadFile]:
        """Upload files to the scratchpad"""
        uploaded_files = []

        try:
            for file in files:
                # Construct file path in storage
                file_path = f"{user_id}/{run_id}/{agent_id}/{file.filename}"

                # Special handling for input files
                if str(agent_id) == INPUT_AGENT_ID:
                    file_path = f"{user_id}/{run_id}/input/{file.filename}"

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

            # Always generate a new signed URL to ensure it's fresh
            # Generate a new signed URL (valid for 1 hour)
            signed_url_result = self.supabase.storage\
                .from_(self.bucket_name)\
                .create_signed_url(file_data["path"], 3600)

            if isinstance(signed_url_result, dict) and "error" in signed_url_result:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to create signed URL: {signed_url_result['error']}"
                )

            if isinstance(signed_url_result, dict) and "signedURL" in signed_url_result:
                url = signed_url_result["signedURL"]
            else:
                url = str(signed_url_result)

            # Update the metadata with the new URL (but don't store back to DB)
            metadata.url = url

            return ScratchpadFileResponse(
                metadata=metadata,
                url=url
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