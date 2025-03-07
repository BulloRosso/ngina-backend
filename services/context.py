# services/context.py
from fastapi import HTTPException, Header
from typing import List, Dict, Any, Optional
from models.context import AgentContext
from services.agents import AgentService
from supabase import create_client
import logging
from pydantic import UUID4
import os
import json
from pathlib import Path
from openai import OpenAI

logger = logging.getLogger(__name__)

class ContextService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        self.agent_service = AgentService()
        self.openai_client = OpenAI()

    async def build_context(self, agent_chain: List[str]) -> str:
        """
        Build and return context information for a chain of agents.

        Args:
            agent_chain: A list of agent IDs

        Returns:
            A dictionary mapping agent IDs to their context information
        """
        try:
            context_dict = {}

            for agent_id in agent_chain:
                agent = await self.agent_service.get_agent(agent_id)

                # Extract English title and description
                title = agent.title.en if agent.title and hasattr(agent.title, "en") else None
                description = agent.description.en if agent.description and hasattr(agent.description, "en") else None

                agent_context = AgentContext(
                    prompt=agent.task_prompt,
                    title=title,
                    description=description,
                    input=agent.input,
                    input_example=agent.input_example,
                    output=agent.output,
                    output_example=agent.output_example
                )

                context_dict[str(agent.id)] = agent_context

            # Prepare context_dict for the LLM with renamed fields
            llm_context_dict = {}
            for agent_id, agent_context in context_dict.items():
                llm_context_dict[agent_id] = {
                    "prompt": agent_context.prompt,
                    "title": agent_context.title,
                    "description": agent_context.description,
                    "input": agent_context.input,
                    "input_data": agent_context.input_example,  # renamed from input_example
                    "output": agent_context.output,
                    "output_data": agent_context.output_example  # renamed from output_example
                }

            # Load the prompt template
            try:
                prompt_path = Path("prompts/transformer-function-builder.txt")
                with open(prompt_path, "r", encoding="utf-8") as f:
                    prompt_template = f.read()
            except Exception as e:
                logger.error(f"Failed to load transformer function builder template: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to load transformer function builder template"
                )

            # Format the prompt
            formatted_prompt = prompt_template.replace("<context_dict>", json.dumps(llm_context_dict, indent=2))
            formatted_prompt = formatted_prompt.replace("<user input>", "Create a function getInputDto(context) for the last agent in the chain")

            # Call the OpenAI API with a reasoning model (medium efforts)
            response = self.openai_client.chat.completions.create(
                model="o3-mini-2025-01-31",
                messages=[
                    {
                        "role": "developer",
                        "content": [
                            {
                                "type": "text",
                                "text": formatted_prompt
                            }
                        ]
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Create a function \"getInputDto()\" for agent " + agent_chain[-1]
                            }
                        ]
                    }
                ],
                response_format={"type": "text"},
                reasoning_effort="medium"
            )

            # Extract the response text
            transformer_function = response.choices[0].message.content.strip()

            # Check if the response is JSON-encoded (surrounded by quotes and contains escaped newlines)
            if (transformer_function.startswith('"') and transformer_function.endswith('"') and "\\n" in transformer_function):
                # This is likely a JSON-encoded string, so decode it
                try:
                    transformer_function = json.loads(transformer_function)
                except json.JSONDecodeError:
                    # If it fails to decode, keep it as is
                    pass
                        
            # Return just the transformer function as plain text
            return transformer_function

        except Exception as e:
            logger.error(f"Error building context: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to build context: {str(e)}")
            
    async def get_context_by_run_id(self, run_id: str, x_ngina_key: Optional[str] = None) -> Dict[str, AgentContext]:
        """
        Get context information for a specific run ID.

        Args:
            run_id: The operation/run ID
            x_ngina_key: API key for authentication

        Returns:
            A dictionary mapping agent IDs to their context information
        """
        try:
            # Validate API key
            workflow_key = os.getenv("NGINA_WORKFLOW_KEY")
            if not workflow_key or x_ngina_key != workflow_key:
                raise HTTPException(status_code=403, detail="Invalid or missing API key")

            # Get the operation from Supabase
            result = self.supabase.table("agent_runs").select("*").eq("id", run_id).execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Run not found")

            run_data = result.data[0]
            agent_id = run_data.get("agent_id")
            prompt = run_data.get("prompt")

            if not agent_id:
                raise HTTPException(status_code=400, detail="Run doesn't have an associated agent")

            # Get the agent
            agent = await self.agent_service.get_agent(agent_id)

            # Build agent chain
            agent_chain = [str(agent.id)]

            # Check if agent has configuration with additional agents in the chain
            if agent.configuration and isinstance(agent.configuration, dict) and "agentChain" in agent.configuration:
                agent_chain.extend(agent.configuration["agentChain"])

            # Build context for all agents in the chain
            context_dict = await self.build_context(agent_chain)

            # Update prompts with the run's prompt
            if prompt:
                for agent_context in context_dict.values():
                    agent_context.prompt = prompt

            return context_dict

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting context by run ID: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get context: {str(e)}")

    def load_prompt_template(self) -> str:
        """Load the prompt-to-json template from file."""
        try:
            prompt_path = Path("prompts/prompt-to-json.md")
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load prompt template: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to load prompt template"
            )

    def validate_required_fields(self, schema: Dict[str, Any], data: Dict[str, Any]) -> List[str]:
        """
        Validate that all required fields are present in the generated JSON.

        Args:
            schema: The JSON schema
            data: The JSON data to validate

        Returns:
            A list of missing required field names
        """
        missing_fields = []

        # Check if schema has a properties field (JSON Schema)
        if "properties" in schema and "required" in schema:
            # Standard JSON Schema format
            for field in schema["required"]:
                if field not in data:
                    missing_fields.append(field)
        else:
            # Custom schema format (key-value pairs where each key is a field)
            for field_name, field_schema in schema.items():
                # Check if field is required
                is_required = False

                # Different ways to determine if a field is required
                if isinstance(field_schema, dict):
                    # Field schema is a dictionary with potential "required" property
                    is_required = field_schema.get("required", False)
                elif hasattr(field_schema, "required") and field_schema.required:
                    # Field schema is an object with a "required" attribute
                    is_required = True

                if is_required and field_name not in data:
                    missing_fields.append(field_name)

        return missing_fields
    
    async def prompt_to_json(self, agent_id: str, user_prompt: str, one_shot: bool = True) -> Dict[str, Any]:
        """
        Convert a user prompt to JSON based on an agent's input schema.

        Args:
            agent_id: The agent ID
            user_prompt: The user's prompt
            one_shot: Whether to use one-shot learning

        Returns:
            The generated JSON object
        """
        try:
            # Get agent details
            agent = await self.agent_service.get_agent(agent_id)

            if not agent.input:
                raise HTTPException(status_code=400, detail="Agent doesn't have an input schema defined")

            # Load the prompt template
            prompt_template = self.load_prompt_template()

            # Format the prompt with agent input schema and examples
            formatted_prompt = prompt_template.replace("<agent.input>", json.dumps(agent.input, indent=2))

            # Add input example if available and one_shot is True
            if one_shot and agent.input_example:
                formatted_prompt = formatted_prompt.replace(
                    "<agent.input_example if not empty>", 
                    json.dumps(agent.input_example, indent=2)
                )
            else:
                formatted_prompt = formatted_prompt.replace("<agent.input_example if not empty>", "")

            # Call the OpenAI API
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": formatted_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                temperature=0.2  # Lower temperature for more deterministic outputs
            )

            # Extract the response text
            response_text = response.choices[0].message.content.strip()

            # Parse the response as JSON
            try:
                json_response = json.loads(response_text)

                # Validate that all required fields are present
                missing_fields = self.validate_required_fields(agent.input, json_response)

                if missing_fields:
                    logger.warning(f"Missing required fields in generated JSON: {missing_fields}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Generated JSON is missing required fields: {', '.join(missing_fields)}"
                    )

                return json_response
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {response_text}")
                raise HTTPException(
                    status_code=422, 
                    detail="LLM generated invalid JSON. Please try again with a more specific prompt."
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in prompt to JSON conversion: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to convert prompt to JSON: {str(e)}")