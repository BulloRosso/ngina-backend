# services/prompts.py
from fastapi import HTTPException
from typing import List, Optional
from models.prompt import Prompt, PromptCreate
from supabase import create_client
import logging
from pydantic import ValidationError, UUID4
import os

logger = logging.getLogger(__name__)

class PromptService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

    async def create_prompt(self, prompt_data: PromptCreate) -> Prompt:
        try:
            # Check if a prompt with the same name exists to determine the version
            existing_prompts = self.supabase.table("prompts") \
                .select("version") \
                .eq("name", prompt_data.name) \
                .order("version", desc=True) \
                .limit(1) \
                .execute()

            # Calculate the next version number
            next_version = 1
            if existing_prompts.data:
                next_version = existing_prompts.data[0]["version"] + 1

            # If this is a new prompt group or we're explicitly setting is_active,
            # we might need to update is_active status
            handle_activation = True
            if prompt_data.is_active:
                # If this prompt is to be active, deactivate others in the group
                await self._deactivate_prompt_group(prompt_data.name)
            elif next_version == 1:
                # First version of a prompt group is active by default
                prompt_data.is_active = True
            else:
                # Don't change activation status for non-first versions
                handle_activation = False

            # Prepare data for insertion
            insert_data = {
                "name": prompt_data.name,
                "prompt_text": prompt_data.prompt_text,
                "version": next_version,
                "is_active": prompt_data.is_active
            }

            # Check if there's an existing prompt with the same text
            if next_version > 1:
                last_prompt = self.supabase.table("prompts") \
                    .select("prompt_text") \
                    .eq("name", prompt_data.name) \
                    .eq("version", next_version - 1) \
                    .execute()

                if last_prompt.data and last_prompt.data[0]["prompt_text"] == prompt_data.prompt_text:
                    raise HTTPException(
                        status_code=400, 
                        detail="New prompt text must be different from the previous version"
                    )

            # Insert the new prompt
            result = self.supabase.table("prompts").insert(insert_data).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="Failed to create prompt")

            return Prompt.model_validate(result.data[0])

        except ValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            raise HTTPException(
                status_code=422,
                detail=f"Data validation error: {str(e)}"
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Error creating prompt: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create prompt: {str(e)}")

    async def get_prompt(self, prompt_id: UUID4) -> Prompt:
        try:
            result = self.supabase.table("prompts") \
                .select("*") \
                .eq("id", str(prompt_id)) \
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Prompt not found")

            return Prompt.model_validate(result.data[0])
        except ValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            raise HTTPException(
                status_code=422,
                detail=f"Data validation error: {str(e)}"
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Error getting prompt: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get prompt: {str(e)}")

    async def get_prompt_by_name(self, name: str) -> Prompt:
        """Get the active prompt for a given name"""
        try:
            result = self.supabase.table("prompts") \
                .select("*") \
                .eq("name", name) \
                .eq("is_active", True) \
                .limit(1) \
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail=f"No active prompt found for name: {name}")

            return Prompt.model_validate(result.data[0])
        except ValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            raise HTTPException(
                status_code=422,
                detail=f"Data validation error: {str(e)}"
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Error getting prompt by name: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get prompt by name: {str(e)}")

    async def get_prompt_by_name_and_version(self, name: str, version: int) -> Prompt:
        """Get a specific version of a prompt by name and version number"""
        try:
            result = self.supabase.table("prompts") \
                .select("*") \
                .eq("name", name) \
                .eq("version", version) \
                .limit(1) \
                .execute()

            if not result.data:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Prompt not found for name: {name} and version: {version}"
                )

            return Prompt.model_validate(result.data[0])
        except ValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            raise HTTPException(
                status_code=422,
                detail=f"Data validation error: {str(e)}"
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Error getting prompt by name and version: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to get prompt by name and version: {str(e)}"
            )

    async def list_prompts(self, limit: int = 100, offset: int = 0) -> List[Prompt]:
        """List all prompts with pagination"""
        try:
            result = self.supabase.table("prompts") \
                .select("*") \
                .order("name", desc=False) \
                .order("version", desc=True) \
                .range(offset, offset + limit - 1) \
                .execute()

            prompts = []
            for item in result.data:
                try:
                    prompt = Prompt.model_validate(item)
                    prompts.append(prompt)
                except ValidationError as e:
                    logger.error(f"Validation error for prompt {item.get('id')}: {str(e)}")
                    # Continue processing other prompts even if one fails
                    continue

            return prompts
        except Exception as e:
            logger.error(f"Error listing prompts: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to list prompts: {str(e)}")

    async def update_prompt(self, prompt_id: UUID4, prompt_data: dict) -> Prompt:
        """
        Update a prompt - this creates a new version rather than updating in-place
        """
        try:
            # First, get the existing prompt
            existing_prompt = await self.get_prompt(prompt_id)

            # Create a new prompt with incremented version
            new_prompt = PromptCreate(
                name=existing_prompt.name,
                prompt_text=prompt_data.get("prompt_text", existing_prompt.prompt_text),
                is_active=prompt_data.get("is_active", existing_prompt.is_active)
            )

            # Create the new version
            return await self.create_prompt(new_prompt)

        except ValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            raise HTTPException(
                status_code=422,
                detail=f"Data validation error: {str(e)}"
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Error updating prompt: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to update prompt: {str(e)}")

    async def delete_prompt(self, prompt_id: UUID4) -> bool:
        """Delete a single prompt by ID"""
        try:
            result = self.supabase.table("prompts") \
                .delete() \
                .eq("id", str(prompt_id)) \
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Prompt not found")

            return True
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Error deleting prompt: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete prompt: {str(e)}")

    async def delete_prompt_group(self, name: str) -> bool:
        """Delete all prompts with the given name (purge)"""
        try:
            result = self.supabase.table("prompts") \
                .delete() \
                .eq("name", name) \
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail=f"No prompts found with name: {name}")

            return True
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Error deleting prompt group: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete prompt group: {str(e)}")

    async def compare_prompts(self, name: str, version1: int, version2: int) -> List[Prompt]:
        """Compare two versions of a prompt"""
        try:
            # Get both prompt versions
            prompt1 = await self.get_prompt_by_name_and_version(name, version1)
            prompt2 = await self.get_prompt_by_name_and_version(name, version2)

            return [prompt1, prompt2]
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error comparing prompts: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to compare prompts: {str(e)}")

    async def activate_prompt(self, name: str, version: int) -> Prompt:
        """Activate a specific version of a prompt and deactivate all others"""
        try:
            # First, verify the prompt exists
            prompt = await self.get_prompt_by_name_and_version(name, version)

            # Deactivate all prompts in the group
            await self._deactivate_prompt_group(name)

            # Activate the specified prompt
            result = self.supabase.table("prompts") \
                .update({"is_active": True}) \
                .eq("id", str(prompt.id)) \
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Prompt not found during activation")

            return Prompt.model_validate(result.data[0])
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error activating prompt: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to activate prompt: {str(e)}")
    
    async def replace_prompt_text(self, name: str, version: int, prompt_text: str) -> Prompt:
        """Replace the text of an existing prompt without creating a new version"""
        try:
            # First, find the prompt by name and version
            result = self.supabase.table("prompts") \
                .select("*") \
                .eq("name", name) \
                .eq("version", version) \
                .limit(1) \
                .execute()

            if not result.data:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Prompt not found for name: {name} and version: {version}"
                )

            # Get the prompt ID
            prompt_id = result.data[0]["id"]

            # Update only the prompt_text field
            update_result = self.supabase.table("prompts") \
                .update({"prompt_text": prompt_text}) \
                .eq("id", prompt_id) \
                .execute()

            if not update_result.data:
                raise HTTPException(status_code=500, detail="Failed to update prompt text")

            return Prompt.model_validate(update_result.data[0])

        except ValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            raise HTTPException(
                status_code=422,
                detail=f"Data validation error: {str(e)}"
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Error replacing prompt text: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to replace prompt text: {str(e)}"
            )
    async def _deactivate_prompt_group(self, name: str) -> None:
        """Helper method to deactivate all prompts in a group"""
        try:
            self.supabase.table("prompts") \
                .update({"is_active": False}) \
                .eq("name", name) \
                .execute()
        except Exception as e:
            logger.error(f"Error deactivating prompt group: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to deactivate prompt group: {str(e)}"
            )