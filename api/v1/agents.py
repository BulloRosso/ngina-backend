# api/v1/agents.py
from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict
from models.agent import Agent, AgentCreate
from supabase import create_client
import logging
from datetime import datetime
from pydantic import ValidationError, UUID4
import os
import httpx
from models.agent import I18nContent, SchemaField

router = APIRouter(prefix="/agents", tags=["agents"])

class AgentService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

    # Update the create_agent method in AgentService class
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
                "image_url": agent_data.get("image_url"),
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

                # Prepare the data structure directly without using Pydantic models
                agent_data = {
                    "title": {
                        "de": discovery_data["metadata"]["title"].get("de"),
                        "en": discovery_data["metadata"]["title"].get("en")
                    },
                    "description": {
                        "de": discovery_data["metadata"]["description"].get("de"),
                        "en": discovery_data["metadata"]["description"].get("en")
                    },
                    "input": {
                        k: {"type": v["type"]} 
                        for k, v in discovery_data["input"].items()
                    },
                    "output": {
                        k: {"type": v["type"], "description": v.get("subtype")} 
                        for k, v in discovery_data["output"].items()
                    },
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
            
    async def get_agent(self, agent_id: str) -> Agent:
        try:
            # Validate UUID format
            UUID4(agent_id)

            result = self.supabase.table("agents")\
                .select("*")\
                .eq("id", agent_id)\
                .execute()

            logging.info(f"Supabase result: {result}")

            if not result.data:
                raise HTTPException(status_code=404, detail="Agent not found")

            try:
                # Add debug logging for the data
                logging.info(f"Raw agent data: {result.data[0]}")
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

            logging.info(f"Raw data from Supabase: {result.data}")  # Add this line

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

    async def update_agent(self, agent_id: UUID4, agent_data: dict) -> Agent:
        try:
            # First validate the input data using AgentCreate model
            agent = AgentCreate.model_validate(agent_data)

            update_data = {
                "title": agent.title.model_dump() if agent.title else None,
                "description": agent.description.model_dump() if agent.description else None,
                "input": agent.input.model_dump() if agent.input else None,
                "output": agent.output.model_dump() if agent.output else None,
                "credits_per_run": agent.credits_per_run,
                "workflow_id": agent.workflow_id,
                "stars": agent.stars,
                "image_url": agent.image_url
            }

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

@router.post("", response_model=Agent)
async def create_agent(agent_data: dict):
    service = AgentService()
    return await service.create_agent(agent_data)

@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str):
    try:
        service = AgentService()
        return await service.get_agent(agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=List[Agent])
async def list_agents(limit: Optional[int] = 100, offset: Optional[int] = 0):
    service = AgentService()
    return await service.list_agents(limit, offset)

@router.put("/{agent_id}", response_model=Agent)
async def update_agent(agent_id: UUID4, agent_data: dict):
    service = AgentService()
    return await service.update_agent(agent_id, agent_data)

@router.delete("/{agent_id}")
async def delete_agent(agent_id: UUID4):
    service = AgentService()
    return await service.delete_agent(agent_id)

@router.post("/discover", response_model=Agent)
async def discover_agent(data: Dict[str, str]):
    if "agentDiscoveryUrl" not in data:
        raise HTTPException(status_code=400, detail="agentDiscoveryUrl is required")

    service = AgentService()
    return await service.discover_agent(data["agentDiscoveryUrl"])