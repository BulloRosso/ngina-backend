# api/v1/context.py
from fastapi import APIRouter, HTTPException, Header, Depends, Response
from typing import Dict, Any, Optional
from models.context import BuildContextRequest, AgentContext, PromptToJsonRequest
from services.context import ContextService
import logging
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/context", tags=["context"])

@router.post("/builder", 
             response_model=str, 
             summary="Build agent context", 
             description="Build context information for a chain of agents", 
             responses={
                200: {"description": "Context built successfully"},
                422: {"description": "Validation error in request data"},
                500: {"description": "Server error during context building"}
             })
async def build_context(request: BuildContextRequest):
    """
    Return the ES6 transformer function
    """
    service = ContextService()
    transformer_function = await service.build_context(request.agentChain)

    return Response(
        content=transformer_function,
        media_type="application/javascript"
    )
    
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

@router.post("/prompt-to-json/{agent_id}", 
             response_class=JSONResponse,
             summary="Convert prompt to JSON", 
             description="Convert a user prompt to JSON based on an agent's input schema", 
             responses={
                200: {"description": "Prompt successfully converted to JSON with all required fields"},
                400: {"description": "Invalid agent ID, missing input schema, or JSON missing required fields"},
                422: {"description": "Failed to parse LLM response as JSON"},
                500: {"description": "Server error during prompt conversion"}
             })
async def prompt_to_json(agent_id: str, request: PromptToJsonRequest):
    """
    Convert a user prompt to JSON based on an agent's input schema.
    """
    service = ContextService()
    result = await service.prompt_to_json(agent_id, request.prompt, request.one_shot)
    return JSONResponse(content=result)