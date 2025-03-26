# api/v1/context.py
from fastapi import APIRouter, HTTPException, Header, Depends, Response, Body
from typing import Dict, Any, Optional, List
from models.context import BuildContextRequest, AgentContext, PromptToJsonRequest, GetAgentInputFromEnvRequest
from services.context import ContextService
import logging
from fastapi.responses import JSONResponse
from uuid import UUID
import random
from pydantic import BaseModel
from services.context import ContextService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/context", tags=["context"])

# Request model for chain simulation
class ChainSimulationRequest(BaseModel):
    prompt: str
    agents: List[str]

class ChainMagicRequest(BaseModel):
    prompt: str
    agents: List[str]
    connector_prompt: str

class ChainCodeRequest(BaseModel):
    prompt: str
    agents: List[str]
    connector_prompt: str
    
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

@router.post("/resolvers/get-agent-input-from-env",
     response_class=JSONResponse,
     summary="Extract agent input from runtime environment",
     description="Search the runtime environment for required input parameters for an agent with a defined input schema",
     responses={
        200: {"description": "Agent input successfully extracted from environment"},
        400: {"description": "Failed to extract required input parameters"},
        403: {"description": "Invalid or missing API key"},
        404: {"description": "Agent or run not found"},
        500: {"description": "Server error during input extraction"}
     })
async def get_agent_input_from_env(request: GetAgentInputFromEnvRequest, x_ngina_key: Optional[str] = Header(None)):
    """
    Extract agent input from runtime environment.

    Args:
        request: Contains agent_id and run_id
        x_ngina_key: API key for authentication

    Returns:
        Extracted input parameters as JSON if successful, error message if not
    """
    service = ContextService()
    result = await service.get_agent_input_from_env(request.agent_id, request.run_id, x_ngina_key)

    # Check if the operation was successful
    if result.get("success", False):
        # Return just the input object with 200 status
        return JSONResponse(content=result["input"])
    else:
        # Return the full ORET response with 400 status
        return JSONResponse(
            status_code=400,
            content=result
        )


@router.post("/resolvers/get-agent-input-transformer-from-env",
     response_model=str,
     summary="Generate input transformer function",
     description="Generate a JavaScript function that transforms the environment into the required agent input format",
     responses={
        200: {"description": "Transformer function generated successfully"},
        400: {"description": "Failed to generate transformer function"},
        403: {"description": "Invalid or missing API key"},
        404: {"description": "Agent or run not found"},
        500: {"description": "Server error during transformer function generation"}
     })
async def get_agent_input_transformer_from_env(request: GetAgentInputFromEnvRequest, x_ngina_key: Optional[str] = Header(None)):
    """
    Generate a JavaScript transformer function that extracts agent input from environment.
    
    Args:
        request: Contains agent_id and run_id
        x_ngina_key: API key for authentication
    
    Returns:
    ES6 JavaScript function as a string
    """
    service = ContextService()
    transformer_function = await service.get_agent_input_transformer_from_env(request.agent_id, request.run_id, x_ngina_key)
    
    return Response(
        content=transformer_function,
        media_type="application/javascript"
        )

@router.post("/simulation/chain/env/{agent_id}",
     response_class=JSONResponse,
     summary="Simulate chain environment",
     description="Simulate a chain environment with previous agents' outputs",
     responses={
        200: {"description": "Chain environment simulation successful"},
        400: {"description": "Invalid request parameters"},
        404: {"description": "Agent not found"},
        500: {"description": "Server error during simulation"}
     })
async def simulate_chain_environment(agent_id: str, request: ChainSimulationRequest):
    """
    Simulate a chain environment with previous agents' outputs.

    Args:
        agent_id: ID of the agent to simulate for
        request: Contains prompt and array of previous agents in the chain

    Returns:
        Simulated chain environment with input parameters and flow data
    """
    try:
        # Use the service to handle the simulation
        service = ContextService()
        response = await service.simulate_chain_environment(agent_id, request.prompt, request.agents)

        # Return the simulation data
        return JSONResponse(content=response)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error simulating chain environment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to simulate chain environment: {str(e)}"
        )

@router.post("/simulation/chain/magic/{agent_id}")
async def simulate_chain_magic(
    agent_id: str,
    request: ChainMagicRequest,
    x_ngina_key: Optional[str] = Header(None)
):
    """
    Simulate a chain's 'magic' transformation using AI to convert environment to agent input.
    """
    try:
        # Create context service
        service = ContextService()

        # Call the service method
        result = await service.simulate_chain_magic(
            agent_id,
            request.prompt,
            request.agents,
            request.connector_prompt
        )

        # Process the result
        if isinstance(result, dict) and "success" in result:
            if result["success"] and "input" in result:
                # Return 200 with the input object
                return result["input"]
            elif not result["success"] and "message" in result:
                # Return 400 with the message
                raise HTTPException(
                    status_code=400,
                    detail=result["message"]
                )

        # Handle unexpected result format
        raise HTTPException(
            status_code=500,
            detail="Unexpected result format from service"
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error in chain magic simulation endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to simulate chain magic: {str(e)}"
        )

@router.post("/simulation/chain/code/{agent_id}")
async def generate_chain_code(
    agent_id: str,
    request: ChainCodeRequest,
    x_ngina_key: Optional[str] = Header(None)
):
    """
    Generate JavaScript transformer code for connecting agents in a chain.
    """
    try:
        # Create context service
        service = ContextService()

        # Call the service method to generate code
        code = await service.generate_transformer_code(
            agent_id,
            request.prompt,
            request.agents,
            request.connector_prompt
        )

        # Return the generated code
        return {
            "code": code
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error generating chain code: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate chain code: {str(e)}"
        )