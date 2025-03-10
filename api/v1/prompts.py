# api/v1/prompts.py
from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional, Dict, Any
from models.prompt import Prompt, PromptCreate, PromptCompare
from pydantic import ValidationError, UUID4
import logging
from services.prompts import PromptService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prompts", tags=["prompts"])

# Create a new prompt
@router.post("", response_model=Prompt, summary="Create a new prompt", 
             description="Create a new prompt with the provided text and name", 
             status_code=201, 
             responses={
                 201: {"description": "Prompt created successfully"},
                 400: {"description": "Bad request - prompt text must be different from previous version"},
                 422: {"description": "Validation error in request data"},
                 500: {"description": "Server error during prompt creation"}
             })
async def create_prompt(prompt_data: PromptCreate):
    service = PromptService()
    return await service.create_prompt(prompt_data)

# Get prompt by ID
@router.get("/{prompt_id}", response_model=Prompt, summary="Get prompt by ID",
            description="Retrieve detailed information about a specific prompt by ID",
            responses={
                200: {"description": "Prompt details retrieved successfully"},
                404: {"description": "Prompt not found"},
                400: {"description": "Invalid UUID format"},
                500: {"description": "Server error"}
            })
async def get_prompt(prompt_id: UUID4):
    service = PromptService()
    return await service.get_prompt(prompt_id)

# Get active prompt by name
@router.get("/{prompt_name}", response_model=Prompt, summary="Get active prompt by name",
            description="Retrieve the currently active prompt for the specified name",
            responses={
                200: {"description": "Active prompt retrieved successfully"},
                404: {"description": "No active prompt found for the specified name"},
                500: {"description": "Server error"}
            })
async def get_prompt_by_name(prompt_name: str):
    service = PromptService()
    return await service.get_prompt_by_name(prompt_name)

# Get specific version of a prompt
@router.get("/{prompt_name}/{version}", response_model=Prompt, summary="Get prompt by name and version",
            description="Retrieve a specific version of a prompt by name and version number",
            responses={
                200: {"description": "Prompt version retrieved successfully"},
                404: {"description": "Prompt version not found"},
                500: {"description": "Server error"}
            })
async def get_prompt_by_name_and_version(prompt_name: str, version: int):
    service = PromptService()
    return await service.get_prompt_by_name_and_version(prompt_name, version)

# List all prompts
@router.get("", response_model=List[Prompt], summary="List all prompts",
            description="Retrieve a paginated list of all available prompts",
            responses={
                200: {"description": "List of prompts retrieved successfully"},
                500: {"description": "Server error"}
            })
async def list_prompts(limit: Optional[int] = 100, offset: Optional[int] = 0):
    service = PromptService()
    return await service.list_prompts(limit, offset)

# Update a prompt (create a new version)
@router.put("/{prompt_id}", response_model=Prompt, summary="Update a prompt",
            description="Update an existing prompt by creating a new version with incremented version number",
            responses={
                200: {"description": "Prompt updated successfully (new version created)"},
                404: {"description": "Prompt not found"},
                400: {"description": "Bad request - prompt text must be different from previous version"},
                422: {"description": "Validation error in request data"},
                500: {"description": "Server error"}
            })
async def update_prompt(prompt_id: UUID4, prompt_data: Dict[str, Any] = Body(...)):
    service = PromptService()
    return await service.update_prompt(prompt_id, prompt_data)

# Delete a prompt
@router.delete("/{prompt_id}", summary="Delete a prompt",
               description="Delete a specific prompt by ID",
               responses={
                   200: {"description": "Prompt deleted successfully"},
                   404: {"description": "Prompt not found"},
                   500: {"description": "Server error"}
               })
async def delete_prompt(prompt_id: UUID4):
    service = PromptService()
    success = await service.delete_prompt(prompt_id)
    return {"success": success, "message": "Prompt deleted successfully"}

# Delete all prompts with a given name (purge)
@router.delete("/purge/{prompt_name}", summary="Purge prompt group",
               description="Delete all prompts with the specified name",
               responses={
                   200: {"description": "Prompt group purged successfully"},
                   404: {"description": "No prompts found with the specified name"},
                   500: {"description": "Server error"}
               })
async def purge_prompt_group(prompt_name: str):
    service = PromptService()
    success = await service.delete_prompt_group(prompt_name)
    return {"success": success, "message": f"All prompts with name '{prompt_name}' purged successfully"}

# Compare two versions of a prompt
@router.get("/compare/{prompt_name}/{version1}/{version2}", response_model=PromptCompare,
            summary="Compare prompt versions",
            description="Compare two versions of a prompt with the same name",
            responses={
                200: {"description": "Prompt versions retrieved for comparison"},
                404: {"description": "One or both prompt versions not found"},
                500: {"description": "Server error"}
            })
async def compare_prompts(prompt_name: str, version1: int, version2: int):
    service = PromptService()
    prompts = await service.compare_prompts(prompt_name, version1, version2)
    return PromptCompare(prompts=prompts)

# Activate a specific version of a prompt
@router.post("/activate/{prompt_name}/{version}", response_model=Prompt,
             summary="Activate prompt version",
             description="Activate a specific version of a prompt and deactivate all others with the same name",
             responses={
                 200: {"description": "Prompt version activated successfully"},
                 404: {"description": "Prompt version not found"},
                 500: {"description": "Server error"}
             })
async def activate_prompt(prompt_name: str, version: int):
    service = PromptService()
    return await service.activate_prompt(prompt_name, version)