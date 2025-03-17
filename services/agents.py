# services/agents.py
from fastapi import HTTPException
from typing import List, Dict, Any
from models.agent import Agent, AgentCreate, I18nContent, SchemaField
from supabase import create_client
import logging
from pydantic import ValidationError, UUID4, BaseModel
import os
import httpx
from genson import SchemaBuilder

logger = logging.getLogger(__name__)

class SchemaGenerationRequest(BaseModel):
    data: Any

class AgentTestRequest(BaseModel):
    input: Dict[str, Any]

def process_schema(data: Any) -> Any:
    """
    Process input/output data into a JSON schema.
    If data already contains a JSON schema, return it as is.
    Otherwise, generate a schema from the data using genson.
    """
    # If it's already a JSON schema, return as is
    if isinstance(data, dict) and isinstance(data.get("$schema"), str) and data.get("$schema").startswith("http://json-schema.org/"):
        return data

    # Generate schema from data using genson
    builder = SchemaBuilder()
    builder.add_object(data)
    schema = builder.to_schema()

    # Extract and add descriptions
    descriptions = extract_field_descriptions(data)
    add_descriptions_to_schema(schema, descriptions)

    return schema

def extract_field_descriptions(example_data):
    """Extract descriptions from a single object"""
    descriptions = {}
    def process_object(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(value, dict):
                    process_object(value, current_path)
                elif isinstance(value, list) and value:
                    # For arrays, only process the first item if it exists
                    if isinstance(value[0], (dict, list)):
                        process_object(value[0], current_path)
                    else:
                        descriptions[current_path] = str(value[0])
                else:
                    descriptions[current_path] = str(value)

    process_object(example_data)
    return descriptions

def add_descriptions_to_schema(schema, descriptions, path=""):
    """Add descriptions to schema fields"""
    if isinstance(schema, dict):
        if schema.get('type') == 'object' and 'properties' in schema:
            for prop_name, prop_schema in schema['properties'].items():
                current_path = f"{path}.{prop_name}" if path else prop_name
                if current_path in descriptions:
                    prop_schema['description'] = descriptions[current_path]
                add_descriptions_to_schema(prop_schema, descriptions, current_path)
        elif schema.get('type') == 'array' and 'items' in schema:
            add_descriptions_to_schema(schema['items'], descriptions, path)

class AgentService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

    async def create_agent(self, agent_data: dict) -> Agent:
        try:
            # Prepare the data for Supabase directly
            insert_data = {
                "title": agent_data.get("title"),
                "description": agent_data.get("description"),
                "input": agent_data.get("input"),
                "output": agent_data.get("output"),
                "credits_per_run": agent_data.get("credits_per_run", 0),
                "workflow_id": agent_data.get("workflow_id"),
                "stars": agent_data.get("stars", 0),
                "icon_svg": agent_data.get("icon_svg"),
                "wrapped_url": agent_data.get("wrapped_url"),
                "max_execution_time_secs": agent_data.get("max_execution_time_secs"),
                "agent_endpoint": agent_data.get("agent_endpoint")
            }

            result = self.supabase.table("agents").insert(insert_data).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="Failed to create agent")

            return Agent.model_validate(result.data[0])

        except Exception as e:
            logging.error(f"Error creating agent: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")

    async def discover_agent(self, discovery_url: str) -> Agent:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    discovery_url, 
                    headers={"Accept": "application/json"},
                    timeout=30.0
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"URL returned status {response.status_code}"
                    )

                try:
                    discovery_data = response.json()
                except ValueError:
                    raise HTTPException(
                        status_code=422,
                        detail=f"URL did not return valid JSON: {response.text[:200]}"
                    )

                # Validate schema version
                if discovery_data.get("schemaName") != "ngina-metadata.0.9":
                    raise HTTPException(
                        status_code=422,
                        detail=f"Agent sent unknown response (incompatible schema): {str(discovery_data)[:200]}"
                    )

                # Process input schema - now handles a single object
                input_schema = process_schema(discovery_data.get("input"))

                # Process output schema - now handles a single object
                output_schema = process_schema(discovery_data.get("output"))

                agent_data = {
                    "title": {
                        "de": discovery_data["metadata"]["title"].get("de"),
                        "en": discovery_data["metadata"]["title"].get("en")
                    },
                    "description": {
                        "de": discovery_data["metadata"]["description"].get("de"),
                        "en": discovery_data["metadata"]["description"].get("en")
                    },
                    "input": input_schema,
                    "output": output_schema,
                    "icon_svg": discovery_data["metadata"].get("icon_svg"),
                    "max_execution_time_secs": discovery_data["metadata"].get("maxRuntimeSeconds"),
                    "agent_endpoint": discovery_url
                }

                # Create the agent using existing method
                return await self.create_agent(agent_data)

        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Agent did not respond: {str(e)}"
            )

    async def test_agent(self, agent_id: str, test_data: AgentTestRequest) -> Dict[str, Any]:
        try:
            logger.info(f"Testing agent {agent_id} with test data: {test_data}")

            # First get the agent to verify it exists and get the endpoint
            agent = await self.get_agent(agent_id)

            if not agent.agent_endpoint:
                raise HTTPException(
                    status_code=400,
                    detail="Agent doesn't have an endpoint configured"
                )

            logger.info(f"Sending validated test data to agent endpoint: {agent.agent_endpoint}")

            # Make the request to the agent endpoint
            async with httpx.AsyncClient() as client:
                
                endpoint = agent.agent_endpoint
                if "/wrapper/" in endpoint:
                    endpoint = agent.workflow_id

                logger.info(f"*** ENDPOINT {endpoint}")
                
                try:
                    logger.info(f"Calling agent endpoint {agent.agent_endpoint} with data {test_data.input}")

                    response = await client.post(
                        agent.agent_endpoint,
                        json=test_data.input,
                        headers={
                            "Accept": "application/json",
                            "Content-Type": "application/json"
                        },
                        timeout=float(agent.max_execution_time_secs or 30.0)
                    )

                    logger.debug(f"Agent endpoint response status: {response.status_code}")
                    logger.debug(f"Agent endpoint response headers: {response.headers}")
                    logger.debug(f"Agent endpoint response content: {response.text[:500]}")

                    # Check if the request was successful
                    response.raise_for_status()

                    # Try to parse the response as JSON
                    result = response.json()
                    
                    return result

                except httpx.TimeoutException:
                    raise HTTPException(
                        status_code=504,
                        detail="Agent execution timed out"
                    )
                except httpx.HTTPStatusError as e:
                        try:
                            error_json = e.response.json()
                            error_detail = error_json.get('detail', str(error_json))
                        except ValueError:
                            error_detail = e.response.text[:200]

                        logger.error(f"Agent endpoint returned error: {error_detail}")
                        raise HTTPException(
                            status_code=e.response.status_code,
                            detail=f"Agent returned error: {error_detail}"
                        )
                except httpx.RequestError as e:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Failed to communicate with agent: {str(e)}"
                    )

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error testing agent: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to test agent: {str(e)}"
            )

    async def get_agent(self, agent_id: str) -> Agent:
        try:
            # Validate UUID format
            UUID4(agent_id)

            result = self.supabase.table("agents")\
                .select("*")\
                .eq("id", agent_id)\
                .execute()

            # logging.info(f"Supabase result: {result}")

            if not result.data:
                raise HTTPException(status_code=404, detail="Agent not found")

            try:
                # Add debug logging for the data
                # logging.info(f"Raw agent data: {result.data[0]}")
                return Agent.model_validate(result.data[0])
            except ValidationError as e:
                logging.error(f"Validation error: {str(e)}")
                raise HTTPException(
                    status_code=422,
                    detail=f"Data validation error: {str(e)}"
                )
            except Exception as e:
                logging.error(f"Error processing agent data: {str(e)}")
                raise
        except ValidationError as e:
            error_messages = []
            for error in e.errors():
                field_path = " -> ".join(str(x) for x in error["loc"])
                error_messages.append({
                    "field": field_path,
                    "error": error["msg"],
                    "type": error["type"]
                })
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation error",
                    "errors": error_messages
                }
            )
        except Exception as e:
            logging.error(f"Error getting agent: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get agent: {str(e)}")

    async def list_agents(self, limit: int = 100, offset: int = 0) -> List[Agent]:
        try:
            result = self.supabase.table("agents")\
                .select("*")\
                .range(offset, offset + limit - 1)\
                .execute()

            # logging.info(f"Raw data from Supabase: {result.data}")

            agents = []
            for item in result.data:
                try:
                    agent = Agent.model_validate(item)
                    agents.append(agent)
                except ValidationError as e:
                    logging.error(f"Validation error for agent {item.get('id')}: {str(e)}")
                    # Continue processing other agents even if one fails
                    continue

            return agents

        except ValidationError as e:
            error_messages = []
            for error in e.errors():
                field_path = " -> ".join(str(x) for x in error["loc"])
                error_messages.append({
                    "field": field_path,
                    "error": error["msg"],
                    "type": error["type"]
                })
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation error",
                    "errors": error_messages
                }
            )
        except Exception as e:
            logging.error(f"Error listing agents: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(e)}")

    # services/agents.py - Updated update_agent method

    async def update_agent(self, agent_id: UUID4, agent_data: dict) -> Agent:
        try:
            # Convert the input dictionaries to model classes only if they're not already models
            if "title" in agent_data and isinstance(agent_data["title"], dict):
                title_data = agent_data["title"]
                title = I18nContent(
                    en=title_data.get("en"),
                    de=title_data.get("de")
                )
                agent_data["title"] = title

            if "description" in agent_data and isinstance(agent_data["description"], dict):
                desc_data = agent_data["description"]
                description = I18nContent(
                    en=desc_data.get("en"),
                    de=desc_data.get("de")
                )
                agent_data["description"] = description

            # Create an AgentCreate model for validation
            agent = AgentCreate(**agent_data)

            # Map the model data back to a dictionary for Supabase
            update_data = {
                "title": agent.title.model_dump() if agent.title else None,
                "description": agent.description.model_dump() if agent.description else None,
                "input": agent_data.get("input"),  # Use original input dictionary
                "output": agent_data.get("output"),  # Use original output dictionary
                "input_example": agent_data.get("input_example"),
                "output_example": agent_data.get("output_example"),
                "credits_per_run": agent.credits_per_run,
                "workflow_id": agent.workflow_id,
                "stars": agent.stars,
                "authentication": agent.authentication,
                "type": agent.type or "atom",
                "icon_svg": agent.icon_svg,
                "wrapped_url": agent.wrapped_url,
                "max_execution_time_secs": agent.max_execution_time_secs,
                "agent_endpoint": agent.agent_endpoint
            }

            logging.info(f"Updating agent with data: {update_data}")

            result = self.supabase.table("agents")\
                .update(update_data)\
                .eq("id", str(agent_id))\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Agent not found")

            return Agent.model_validate(result.data[0])
        except ValidationError as e:
            error_messages = []
            for error in e.errors():
                field_path = " -> ".join(str(x) for x in error["loc"])
                error_messages.append({
                    "field": field_path,
                    "error": error["msg"],
                    "type": error["type"]
                })
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation error",
                    "errors": error_messages
                }
            )
        except Exception as e:
            logging.error(f"Error updating agent: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(e)}")

    async def delete_agent(self, agent_id: UUID4) -> bool:
        try:
            result = self.supabase.table("agents")\
                .delete()\
                .eq("id", str(agent_id))\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Agent not found")

            return True
        except Exception as e:
            logging.error(f"Error deleting agent: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete agent: {str(e)}")

    async def generate_json_schema(self, data: Any) -> Dict[str, Any]:
        """
        Generate a JSON schema from an example object.
        Uses the process_schema method to generate a schema.
        """
        try:
            schema = process_schema(data)
            return schema
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to generate schema: {str(e)}"
            )