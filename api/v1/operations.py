# api/v1/operations.py
from fastapi import APIRouter, HTTPException, Depends, Request, Header, Body
from typing import List, Optional, Dict, Any
from models.operation import Operation, OperationCreate, TeamStatus
from models.human_in_the_loop import HumanInTheLoop, HumanFeedbackStatus
from services.operations import OperationService
from dependencies.auth import get_current_user
import logging
import json
from pydantic import UUID4

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/operations", tags=["operations"])

@router.post("/run", response_model=Operation)
async def create_or_update_operation(operation_data: dict, current_user: UUID4 = Depends(get_current_user)):
    # Add the user_id to the operation data
    operation_data["user_id"] = str(current_user)

    service = OperationService()
    return await service.create_or_update_operation(operation_data)

@router.get("/run/{operation_id}", response_model=Operation)
async def get_operation(operation_id: int, current_user: UUID4 = Depends(get_current_user)):
    service = OperationService()
    return await service.get_operation(operation_id)

@router.delete("/run/{operation_id}")
async def delete_operation(operation_id: int, current_user: UUID4 = Depends(get_current_user)):
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

@router.get("/workflow/{run_id}/env")
async def get_workflow_env(run_id: str, current_user: UUID4 = Depends(get_current_user)):
    """Get workflow environment for a specific run_id"""
    service = OperationService()
    return await service.get_workflow_env(run_id)

@router.post("/workflow/{run_id}/results/{agent_id}")
async def process_workflow_results(
    request: Request,
    run_id: str,
    agent_id: str,
    x_ngina_key: Optional[str] = Header(None)
):
    """Process workflow results and store them using the scratchpads service"""
    try:
        # Get the raw JSON from the request body
        body_json = await request.json()

        # Log the received data for debugging
        logging.info(f"Received JSON data for run_id: {run_id}, agent_id: {agent_id}")

        service = OperationService()
        return await service.process_workflow_results(run_id, agent_id, body_json, x_ngina_key)
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON in request body: {str(e)}"
        )
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/workflow/{run_id}/request-human-feedback/{agent_id}")
async def request_human_feedback(
    request: Request,
    run_id: str,
    agent_id: str,
    x_ngina_key: Optional[str] = Header(None)
):
    """Request human feedback for a workflow and send notification email"""
    try:
        service = OperationService()

        # Check API key authorization
        if x_ngina_key != service.ngina_workflow_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

        # Get the JSON data (could be raw or parsed depending on request)
        try:
            # First try to get JSON directly
            request_data = await request.json()
        except json.JSONDecodeError:
            # If that fails, try to parse the body as form data
            form_data = await request.form()
            request_data = dict(form_data)

        # Handle nested body structure if present
        if isinstance(request_data, dict) and "body" in request_data and isinstance(request_data["body"], dict):
            request_data = request_data["body"]

        logging.info(f"Processed request data: {request_data}")

        # Pass the raw data dict directly to the service method
        return await service.request_human_feedback(run_id, agent_id, request_data)
    except Exception as e:
        logging.error(f"Error in request_human_feedback endpoint: {str(e)}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/human-feedback/{hitl_id}")
async def get_human_feedback(hitl_id: UUID4, current_user: UUID4 = Depends(get_current_user)):
    """Get details of a human-in-the-loop request"""
    service = OperationService()
    return await service.get_human_feedback(hitl_id)

@router.post("/human-feedback/{hitl_id}/update")
async def update_human_feedback(
    request: Request,
    hitl_id: UUID4,
    current_user: UUID4 = Depends(get_current_user)
):
    """Update the status of a human-in-the-loop request"""
    try:
        # Parse the request body
        body_data = await request.json()
        logging.info(f"Received update request body: {body_data}")

        status_str = body_data.get("status")
        reason = body_data.get("reason")

        # Map the status string to enum value
        status_mapping = {
            "approved": HumanFeedbackStatus.APPROVED,
            "rejected": HumanFeedbackStatus.REJECTED
        }

        status = status_mapping.get(status_str)
        if not status:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid status: {status_str}. Must be one of: approved, rejected"
            )

        # Log the intent to update the feedback
        logging.info(f"Updating human feedback ID {hitl_id} with status {status.value} and reason: {reason}")

        service = OperationService()
        result = await service.update_human_feedback(hitl_id, status, reason)

        # Log successful update
        logging.info(f"Successfully updated human feedback ID {hitl_id}")

        return result
    except Exception as e:
        logging.error(f"Error updating human feedback: {str(e)}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/run/{run_id}/status")
async def update_operation_status(
    request: Request,
    run_id: str,
    x_ngina_key: Optional[str] = Header(None)
):
    """Update the status of an operation with debug information"""
    try:
        # Get the raw JSON from the request body
        body_json = await request.json()

        # Log the received data for debugging
        logging.info(f"Received status update for run_id: {run_id}")

        # Validate required fields
        if "status" not in body_json:
            raise HTTPException(
                status_code=400,
                detail="Missing required field 'status'"
            )

        status = body_json.get("status")
        debug_info = body_json.get("debug_info", {})

        # Validate status value
        if status not in ["success", "failure"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid status value. Must be 'success' or 'failure'"
            )

        service = OperationService()
        return await service.update_operation_status(run_id, status, debug_info, x_ngina_key)
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON in request body: {str(e)}"
        )
    except Exception as e:
        logging.error(f"Unexpected error updating operation status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )