# api/v1/operations.py
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any
from models.operation import Operation, OperationCreate, TeamStatus, AgentStatus
from supabase import create_client
import logging
from datetime import datetime, timezone
from pydantic import ValidationError, UUID4
from dependencies.auth import get_current_user
import os
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/operations", tags=["operations"])

class OperationService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
    async def get_team_status(self, user_id: UUID4) -> TeamStatus:
        try:
            logging.info("Starting get_team_status")
            user_id_str = str(user_id)

            # Get team
            team_result = self.supabase.table("teams")\
                .select("agents")\
                .eq("owner_id", user_id_str)\
                .execute()

            logging.info(f"Team query result: {team_result}")

            if not team_result.data:
                logging.info("No team found for user")
                return TeamStatus(agents=[])

            # Extract agent IDs from team
            agents_data = team_result.data[0].get("agents", {})
            members = agents_data.get("members", [])
            agent_ids = [member["agentId"] for member in members if isinstance(member, dict) and "agentId" in member]

            if not agent_ids:
                logging.info("No agent IDs found in team")
                return TeamStatus(agents=[])

            logging.info(f"Found agent IDs: {agent_ids}")

            # Get agent details
            agents_result = self.supabase.table("agents")\
                .select("id,title")\
                .in_("id", agent_ids)\
                .execute()

            logging.info(f"Agents query result: {agents_result}")

            if not agents_result.data:
                logging.info("No agents found")
                return TeamStatus(agents=[])

            # Process each agent
            agent_statuses = []
            for agent_data in agents_result.data:
                agent_id = agent_data["id"]
                title = agent_data.get("title", {}).get("en", "Untitled")

                # Get latest run
                latest_run = self.supabase.table("agent_runs")\
                    .select("*")\
                    .eq("agent_id", agent_id)\
                    .order("created_at", desc=True)\
                    .limit(1)\
                    .execute()

                last_run = None
                if latest_run.data:
                    run = latest_run.data[0]
                    created_at = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))

                    if run["finished_at"]:
                        finished_at = datetime.fromisoformat(run["finished_at"].replace("Z", "+00:00"))
                        duration = int((finished_at - created_at).total_seconds())
                    else:
                        # Fix: Use timezone-aware datetime.now()
                        duration = int((datetime.now(timezone.utc) - created_at).total_seconds())

                    last_run = {
                        "startedAt": run["created_at"],
                        "finishedAt": run["finished_at"],
                        "duration": duration,
                        "workflowId": run["workflow_id"],
                        "status": run["status"],
                        "results": run["results"]
                    }

                agent_statuses.append(
                    AgentStatus(
                        title=title,
                        lastRun=last_run
                    )
                )

            # Sort by title
            agent_statuses.sort(key=lambda x: x.title.lower())

            return TeamStatus(agents=agent_statuses)

        except Exception as e:
            logging.error(f"Error in get_team_status: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to get team status: {str(e)}"
            )

    
    async def create_or_update_operation(self, operation_data: dict) -> Operation:
        try:
            # Check if operation exists based on workflow_id (assuming this is the unique identifier)
            if operation_data.get("workflow_id"):
                existing = self.supabase.table("agent_runs")\
                    .select("*")\
                    .eq("workflow_id", operation_data["workflow_id"])\
                    .execute()

                if existing.data:
                    # Update existing operation
                    result = self.supabase.table("agent_runs")\
                        .update({
                            "agent_id": operation_data.get("agent_id"),
                            "results": operation_data.get("results"),
                            "status": operation_data.get("status"),
                            "sum_credits": operation_data.get("sum_credits"),
                            "finished_at": operation_data.get("finished_at"),
                        })\
                        .eq("workflow_id", operation_data["workflow_id"])\
                        .execute()
                else:
                    # Create new operation
                    result = self.supabase.table("agent_runs")\
                        .insert(operation_data)\
                        .execute()

                if not result.data:
                    raise HTTPException(status_code=500, detail="Failed to create/update operation")

                return Operation.model_validate(result.data[0])

            else:
                # Create new operation without workflow_id
                result = self.supabase.table("agent_runs")\
                    .insert(operation_data)\
                    .execute()

                if not result.data:
                    raise HTTPException(status_code=500, detail="Failed to create operation")

                return Operation.model_validate(result.data[0])

        except Exception as e:
            logging.error(f"Error creating/updating operation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create/update operation: {str(e)}")

    async def get_operation(self, operation_id: int) -> Operation:
        try:
            result = self.supabase.table("agent_runs")\
                .select("*")\
                .eq("id", operation_id)\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Operation not found")

            return Operation.model_validate(result.data[0])

        except Exception as e:
            logging.error(f"Error getting operation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get operation: {str(e)}")

    async def delete_operation(self, operation_id: int) -> bool:
        try:
            result = self.supabase.table("agent_runs")\
                .delete()\
                .eq("id", operation_id)\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Operation not found")

            return True

        except Exception as e:
            logging.error(f"Error deleting operation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete operation: {str(e)}")

@router.post("/run", response_model=Operation)
async def create_or_update_operation(operation_data: dict):
    service = OperationService()
    return await service.create_or_update_operation(operation_data)

@router.get("/run/{operation_id}", response_model=Operation)
async def get_operation(operation_id: int):
    service = OperationService()
    return await service.get_operation(operation_id)

@router.delete("/run/{operation_id}")
async def delete_operation(operation_id: int):
    service = OperationService()
    return await service.delete_operation(operation_id)

@router.get("/team-status", response_model=TeamStatus)
async def get_team_status(current_user: UUID4 = Depends(get_current_user)):
    try:
        service = OperationService()
        return await service.get_team_status(current_user)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))