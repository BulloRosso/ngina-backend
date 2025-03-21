# services/context.py
from fastapi import HTTPException, Header
from typing import List, Dict, Any, Optional
from models.context import AgentContext
from services.agents import AgentService
from supabase import create_client
import logging
from uuid import UUID
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
                                "text": "Create a function \"transform_input(context)\" for agent " + agent_chain[-1]
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

    async def get_agent_input_from_env(self, agent_id: UUID, run_id: UUID, x_ngina_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract agent input from runtime environment.

        Args:
            agent_id: UUID of the agent
            run_id: UUID of the run
            x_ngina_key: API key for authentication

        Returns:
            Dictionary containing success flag, optional message, and input JSON if successful
        """
        try:
            # 1. Load the runtime environment from agent_runs table
            # Validate API key
            workflow_key = os.getenv("NGINA_WORKFLOW_KEY")
            if not workflow_key or x_ngina_key != workflow_key:
                raise HTTPException(status_code=403, detail="Invalid or missing API key")

            # Get the run data from Supabase
            result = self.supabase.table("agent_runs").select("*").eq("id", str(run_id)).execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Run not found")

            run_data = result.data[0]

            # Extract the results field which contains the runtime environment
            runtime_env = run_data.get("results", {})

            if not runtime_env:
                logger.warning(f"Run {run_id} has no results data")
                return {
                    "success": False,
                    "message": "No runtime environment data available for this run"
                }

            # 2. Load the agent
            agent_service = AgentService()
            agent = await agent_service.get_agent(str(agent_id))

            if not agent.input:
                raise HTTPException(
                    status_code=400, 
                    detail="Agent doesn't have an input schema defined"
                )

            # 3. Load the prompt template
            try:
                prompt_path = Path("prompts/get-agent-input-from-env.md")
                with open(prompt_path, "r", encoding="utf-8") as f:
                    prompt_template = f.read()
            except Exception as e:
                logger.error(f"Failed to load input extraction prompt template: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to load input extraction prompt template"
                )

            # 4. Replace placeholders in the prompt
            formatted_prompt = prompt_template.replace("{agent.input}", json.dumps(agent.input, indent=2))
            formatted_prompt = formatted_prompt.replace("{runtime-env}", json.dumps(runtime_env, indent=2))

            # 5. Call the OpenAI API with gpt-4o-mini model
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": formatted_prompt
                    }
                ],
                temperature=0.1 # Lower temperature for more deterministic outputs
            )

            # Extract the response text
            response_text = response.choices[0].message.content.strip()

            # 6. Parse the response as JSON
            try:
                result = json.loads(response_text)

                # Validate that the result has the expected format
                if "success" not in result:
                    logger.error(f"LLM response missing 'success' field: {response_text}")
                    return {
                        "success": False,
                        "message": "Invalid response format from LLM: missing 'success' field"
                    }

                if result["success"] and "input" not in result:
                    logger.error(f"LLM successful response missing 'input' field: {response_text}")
                    return {
                        "success": False,
                        "message": "Invalid response format from LLM: successful response missing 'input' field"
                    }

                if not result["success"] and "message" not in result:
                    logger.error(f"LLM error response missing 'message' field: {response_text}")
                    return {
                        "success": False,
                        "message": "Invalid response format from LLM: error response missing 'message' field"
                    }

                # If successful, validate that all required fields are present in the input
                if result["success"]:
                    missing_fields = self.validate_required_fields(agent.input, result["input"])

                    if missing_fields:
                        logger.warning(f"Missing required fields in extracted input: {missing_fields}")
                        return {
                            "success": False,
                            "message": f"Extracted input is missing required fields: {', '.join(missing_fields)}"
                        }

                return result

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {response_text}")
                return {
                    "success": False,
                    "message": "LLM generated invalid JSON. Please try again."
                }

        except HTTPException as e:
            # Propagate HTTP exceptions with their status codes
            raise
        except Exception as e:
            logger.error(f"Error extracting agent input from environment: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to extract agent input: {str(e)}"
            }

    async def get_agent_input_transformer_from_env(self, agent_id: UUID, run_id: UUID, x_ngina_key: Optional[str] = None) -> str:
        """
        Generate a JavaScript transformer function that extracts agent input from environment.
    
        Args:
            agent_id: UUID of the agent
            run_id: UUID of the run
            x_ngina_key: API key for authentication
    
        Returns:
            ES6 JavaScript function as a string
        """
        try:
            # 1. Validate API key
            workflow_key = os.getenv("NGINA_WORKFLOW_KEY")
            if not workflow_key or x_ngina_key != workflow_key:
                raise HTTPException(status_code=403, detail="Invalid or missing API key")
    
            # 2. Get the run data from Supabase
            result = self.supabase.table("agent_runs").select("*").eq("id", str(run_id)).execute()
    
            if not result.data:
                raise HTTPException(status_code=404, detail="Run not found")
    
            run_data = result.data[0]
    
            # Extract the results field which contains the runtime environment
            runtime_env = run_data.get("results", {})
    
            if not runtime_env:
                raise HTTPException(
                    status_code=400, 
                    detail="No runtime environment data available for this run"
                )
    
            # 3. Load the agent
            agent_service = AgentService()
            agent = await agent_service.get_agent(str(agent_id))
    
            if not agent.input:
                raise HTTPException(
                    status_code=400, 
                    detail="Agent doesn't have an input schema defined"
                )
    
            # 4. Load the prompt template
            try:
                prompt_path = Path("prompts/get-agent-input-transformer-from-env.md")
                with open(prompt_path, "r", encoding="utf-8") as f:
                    prompt_template = f.read()
            except Exception as e:
                logger.error(f"Failed to load transformer function prompt template: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to load transformer function prompt template"
                )
    
            # 5. Replace placeholders in the prompt
            formatted_prompt = prompt_template.replace("{agent.input}", json.dumps(agent.input, indent=2))
            formatted_prompt = formatted_prompt.replace("{runtime-env}", json.dumps(runtime_env, indent=2))
    
            # 6. Call the OpenAI API (using a more capable model for code generation)
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": formatted_prompt
                    }
                ],
                temperature=0.2  # Lower temperature for more deterministic outputs
            )
    
            # Extract the response text
            transformer_function = response.choices[0].message.content.strip()
    
            # Check if the response starts with ```javascript and ends with ```
            if transformer_function.startswith("```javascript") or transformer_function.startswith("```js"):
                # Extract the code between the backticks
                transformer_function = transformer_function.split("```")[1]
                if transformer_function.startswith("javascript") or transformer_function.startswith("js"):
                    transformer_function = transformer_function[transformer_function.find("\n"):]
    
            elif transformer_function.startswith("```") and transformer_function.endswith("```"):
                # Extract the code between the backticks
                transformer_function = transformer_function[3:-3]
    
            # Clean up the function by removing any extra text
            # Check if it contains a function declaration
            function_start = transformer_function.find("function transform")
            if function_start != -1:
                transformer_function = transformer_function[function_start:]
    
            # Check for const/let transform =
            const_start = transformer_function.find("const transform")
            if const_start != -1:
                transformer_function = transformer_function[const_start:]
    
            let_start = transformer_function.find("let transform")
            if let_start != -1:
                transformer_function = transformer_function[let_start:]
    
            # Make sure the function ends properly
            if transformer_function.strip() and not transformer_function.strip().endswith(";"):
                # Add a semicolon if missing
                transformer_function = transformer_function.rstrip() + ";"
    
            return transformer_function.strip()
    
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error generating transformer function: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to generate transformer function: {str(e)}"
            )