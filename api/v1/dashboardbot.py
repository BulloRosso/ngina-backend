# api/v1/dashboardbot.py
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, Literal, Dict, Any, Union
from uuid import UUID, uuid4
import logging
import os
import httpx
from services.agents import AgentService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboardbot", tags=["bots"])

class ChatbotRequest(BaseModel):
    sessionId: str
    action: str
    chatInput: str
    language: Optional[str] = "en"
    agentId: Optional[str] = None

class ChatbotResponse(BaseModel):
    answer: str

# Main endpoint for dashboard chatbot requests
@router.post("", response_model=ChatbotResponse)
async def process_chat_request(
    request: Union[ChatbotRequest, Dict[str, Any]]
) -> ChatbotResponse:
    """
    Process chat requests and forward them to the appropriate agent.
    """
    try:
        # Extract data from request
        if isinstance(request, dict):
            session_id = request.get("sessionId", str(uuid4()))
            message = request.get("chatInput", "")
            action = request.get("action", "sendMessage")
            agent_id = request.get("agentId")
        else:
            session_id = request.sessionId
            message = request.chatInput
            action = request.action
            agent_id = request.agentId

        # Only process if action is sendMessage
        if action != "sendMessage":
            return ChatbotResponse(answer="Invalid action")

        # Use default agent ID if none provided
        if not agent_id:
            # You might want to configure a default agent ID here
            agent_id = os.getenv("DEFAULT_CHATBOT_AGENT_ID")
            if not agent_id:
                logger.error("No agent ID provided and no default agent configured")
                return ChatbotResponse(answer="No agent specified for this chatbot")

        # Initialize the agent service and get the agent
        agent_service = AgentService()
        try:
            agent = await agent_service.get_agent(agent_id)
        except HTTPException as e:
            logger.error(f"Error retrieving agent {agent_id}: {e.detail}")
            return ChatbotResponse(answer=f"Agent not found: {e.detail}")
        except Exception as e:
            logger.error(f"Unexpected error retrieving agent {agent_id}: {str(e)}")
            return ChatbotResponse(answer="Error retrieving agent configuration")

        # Check if the agent has an endpoint configured
        if not agent.agent_endpoint:
            logger.error(f"Agent {agent_id} does not have an endpoint configured")
            return ChatbotResponse(answer="This agent is not properly configured")

        logger.info(f"Processing message for agent {agent_id} (endpoint: {agent.agent_endpoint})")

        # Prepare the request to the agent endpoint
        try:
            # Forward the original request payload to the agent
            async with httpx.AsyncClient() as client:
                # Create the payload to send to the agent endpoint
                payload = {
                    "sessionId": session_id,
                    "action": action,
                    "chatInput": message
                }

                # Send the request to the agent endpoint
                response = await client.post(
                    agent.agent_endpoint,
                    json=payload,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    },
                    timeout=float(agent.max_execution_time_secs or 30.0)
                )

                # Check the response
                if response.status_code != 200:
                    logger.error(f"Agent endpoint returned status code {response.status_code}: {response.text}")
                    return ChatbotResponse(answer=f"The agent returned an error ({response.status_code})")

                # Parse the response
                try:
                    response_data = response.json()
                    logger.info(f"Agent response: {response_data}")

                    # Handle array response (like [{"output": "message"}])
                    if isinstance(response_data, list) and len(response_data) > 0:
                        first_item = response_data[0]
                        if isinstance(first_item, dict) and "output" in first_item:
                            return ChatbotResponse(answer=first_item["output"])

                    # Extract the output from the response (original logic)
                    # The agent returns { "output": "<bot response text>" }
                    if isinstance(response_data, dict):
                        # Get the response from the "output" field
                        if "output" in response_data:
                            return ChatbotResponse(answer=response_data["output"])
                        else:
                            # If output field is missing, log a warning and return whatever we got
                            logger.warning(f"Agent response missing 'output' field: {response_data}")
                            # Try to find any text field in the response as fallback
                            answer = response_data.get("answer") or response_data.get("response") or response_data.get("message")

                            if answer:
                                return ChatbotResponse(answer=answer)
                            else:
                                # Last resort: return a string representation of the response
                                return ChatbotResponse(answer=f"Unexpected response format: {str(response_data)}")
                    else:
                        # If the response is not a dict or a list with expected structure, convert it to a string
                        return ChatbotResponse(answer=str(response_data))

                except Exception as e:
                    logger.error(f"Error parsing agent response: {str(e)}")
                    return ChatbotResponse(answer=f"Error processing agent response: {str(e)}")

        except httpx.TimeoutException:
            logger.error(f"Request to agent {agent_id} timed out")
            return ChatbotResponse(answer="The agent took too long to respond")

        except Exception as e:
            logger.error(f"Error sending request to agent {agent_id}: {str(e)}")
            return ChatbotResponse(answer=f"Error communicating with the agent: {str(e)}")

    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        return ChatbotResponse(answer="Sorry, an error occurred while processing your request")

# Agent-specific endpoint
@router.post("/agent/{agent_id}")
async def process_agent_chat(
    agent_id: str,
    request: Union[ChatbotRequest, Dict[str, Any]]
) -> ChatbotResponse:
    """
    Process chat requests for a specific agent.
    """
    # If the request came as a dict, add the agent_id to it
    if isinstance(request, dict):
        request["agentId"] = agent_id
    else:
        request.agentId = agent_id

    # Forward to the main endpoint
    return await process_chat_request(request, user_id)