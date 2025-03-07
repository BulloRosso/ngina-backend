# services/context.py
from fastapi import HTTPException, Header
from typing import List, Dict, Any, Optional
from models.context import AgentContext
from services.agents import AgentService
from supabase import create_client
import logging
from pydantic import UUID4
import os

logger = logging.getLogger(__name__)

class ContextService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        self.agent_service = AgentService()

    async def build_context(self, agent_chain: List[str]) -> Dict[str, AgentContext]:
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

            return context_dict

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