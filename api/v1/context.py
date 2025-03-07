# api/v1/context.py
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Dict, Any, Optional
from models.context import BuildContextRequest, AgentContext
from services.context import ContextService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/context", tags=["context"])

@router.post("/builder", 
             response_model=Dict[str, AgentContext], 
             summary="Build agent context", 
             description="Build context information for a chain of agents", 
             responses={
                200: {"description": "Context built successfully"},
                422: {"description": "Validation error in request data"},
                500: {"description": "Server error during context building"}
             })
async def build_context(request: BuildContextRequest):
    """
    Build and return context information for a chain of agents.
    """
    service = ContextService()
    return await service.build_context(request.agentChain)

@router.get("/{run_id}", 
            response_model=Dict[str, AgentContext], 
            summary="Get context by run ID", 
            description="Get context information for a specific run ID", 
            responses={
                200: {"description": "Context retrieved successfully"},
                403: {"description": "Invalid or missing API key"},
                404: {"description": "Run not found"},
                500: {"description": "Server error during context retrieval"}
            })
async def get_context_by_run_id(
    run_id: str, 
    x_ngina_key: Optional[str] = Header(None)
):
    """
    Get context information for a specific run ID.
    Protected by NGINA_WORKFLOW_KEY.
    """
    service = ContextService()
    return await service.get_context_by_run_id(run_id, x_ngina_key)