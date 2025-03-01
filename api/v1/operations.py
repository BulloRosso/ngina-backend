# api/v1/operations.py
from fastapi import APIRouter, HTTPException, Depends, Request, Header, Body
from typing import List, Optional, Dict, Any
from models.operation import Operation, OperationCreate, TeamStatus, AgentStatus
from supabase import create_client
import logging
from datetime import datetime, timezone
from pydantic import ValidationError, UUID4
from dependencies.auth import get_current_user
import os
import httpx
import json
from models.human_in_the_loop import HumanInTheLoop, HumanInTheLoopCreate, HumanFeedbackStatus, EmailSettings
from services.email import EmailService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/operations", tags=["operations"])

class OperationService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        self.ngina_url = os.getenv("NGINA_URL")
        self.ngina_workflow_key = os.getenv("NGINA_WORKFLOW_KEY")
        self.ngina_scratchpad_key = os.getenv("NGINA_SCRATCHPAD_KEY")

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

                    # Add run_id to the lastRun object
                    last_run = {
                        "run_id": str(run["id"]),  # Add the run_id field
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

    async def get_workflow_env(self, run_id: str) -> Dict[str, Any]:
        """Get workflow environment for a specific run_id"""
        try:
            # Get run record from the supabase table
            result = self.supabase.table("agent_runs")\
                .select("*")\
                .eq("id", run_id)\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Run not found")

            run_data = result.data[0]

            # Extract sub_agents field (JSONB field)
            sub_agents = run_data.get("sub_agents", {})

            # Build response JSON
            response = {
                "nginaUrl": self.ngina_url,
                "ngina_workflow_key": self.ngina_workflow_key,
                "run_id": run_id
            }

            # Add agents list from sub_agents if available
            if sub_agents and "agents" in sub_agents:
                response["agents"] = sub_agents["agents"]

            return response

        except Exception as e:
            logging.error(f"Error getting workflow environment: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to get workflow environment: {str(e)}"
            )

    async def process_workflow_results(self, run_id: str, agent_id: str, results: Dict[str, Any], api_key: str) -> Dict[str, Any]:
        """Process workflow results and store them using the scratchpads service"""
        try:
            # Verify API key
            if api_key != self.ngina_workflow_key:
                raise HTTPException(
                    status_code=401, 
                    detail="Invalid API key"
                )

            # Get the run details from the agent_runs table
            run_result = self.supabase.table("agent_runs")\
                .select("*")\
                .eq("id", run_id)\
                .execute()

            if not run_result.data:
                raise HTTPException(status_code=404, detail="Run not found")

            # Get the user_id associated with this run
            user_id = run_result.data[0].get("user_id")

            if not user_id:
                raise HTTPException(
                    status_code=400,
                    detail="No user associated with this run"
                )

            # Use httpx to call the scratchpads endpoint
            async with httpx.AsyncClient() as client:
                headers = {
                    "x-ngina-key": self.ngina_scratchpad_key,
                }

                # Use the user's ID instead of a system ID
                base_url = f"{self.ngina_url}/api/v1/scratchpads/{user_id}/{run_id}/{agent_id}"

                # Log request details for debugging
                logging.info(f"Base scratchpad URL: {base_url} for user_id: {user_id}")

                # First, store the original JSON results
                json_str = json.dumps(results)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"results_{timestamp}.json"

                # Create a multipart form with files field for the JSON
                files = {
                    "files": (filename, json_str, "application/json")
                }

                # Make POST request to the scratchpads endpoint with JSON file
                response = await client.post(
                    base_url, 
                    files=files,
                    headers=headers
                )

                # Log response for debugging
                logging.info(f"JSON storage response status: {response.status_code}")

                if response.status_code != 200:
                    error_detail = response.json() if response.headers.get("content-type") == "application/json" else response.text
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Failed to store results: {error_detail}"
                    )

                # Now analyze the results for URLs and download/store each file
                url_files_found = []

                # Helper function to recursively find URL properties in nested dictionaries
                def find_url_properties(obj, path=""):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            new_path = f"{path}.{key}" if path else key

                            # Check if property ends with _url and value is an HTTP URL
                            if (key.endswith("_url") and 
                                isinstance(value, str) and 
                                value.startswith("http")):
                                url_files_found.append((new_path, value))

                            # Recursively search nested objects
                            find_url_properties(value, new_path)
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            new_path = f"{path}[{i}]"
                            find_url_properties(item, new_path)

                # Find all URL properties in the results
                find_url_properties(results)

                logging.info(f"Found {len(url_files_found)} URL properties to download")

                # Download and store each file separately
                processed_files = []
                for path, url in url_files_found:
                    try:
                        logging.info(f"Downloading file from URL: {url}")

                        # Download the file
                        file_response = await client.get(url)

                        if file_response.status_code != 200:
                            logging.warning(f"Failed to download file from {url}: {file_response.status_code}")
                            continue

                        # Get content type and file data
                        content_type = file_response.headers.get("content-type", "application/octet-stream")
                        file_data = file_response.content

                        # Generate filename based on URL
                        url_parts = url.split("/")
                        url_filename = url_parts[-1].split("?")[0]  # Remove query parameters
                        if not url_filename:
                            # Fallback filename if URL doesn't have a clear filename
                            url_filename = f"file_{len(processed_files)}_{timestamp}"

                        # Create a multipart form for this single file
                        file_files = {
                            "files": (url_filename, file_data, content_type)
                        }

                        # Post the file to scratchpads
                        file_post_response = await client.post(
                            base_url,
                            files=file_files,
                            headers=headers
                        )

                        if file_post_response.status_code != 200:
                            logging.warning(f"Failed to store file from {url}: {file_post_response.status_code}")
                            continue

                        processed_files.append({
                            "path": path,
                            "url": url,
                            "mime_type": content_type,
                            "filename": url_filename
                        })

                        logging.info(f"Successfully stored file from {url} with type {content_type}")

                    except Exception as e:
                        logging.error(f"Error processing URL {url}: {str(e)}")

                return {
                    "message": "Results successfully stored",
                    "run_id": run_id,
                    "agent_id": str(agent_id),
                    "user_id": user_id,
                    "downloaded_files": len(processed_files),
                    "url_properties_found": len(url_files_found)
                }
        except Exception as e:
            logging.error(f"Error processing workflow results: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process workflow results: {str(e)}"
            )

    async def request_human_feedback(self, run_id: str, agent_id: str, data: Dict[str, Any]) -> HumanInTheLoop:
        """Create a human-in-the-loop request and send notification email"""
        try:
            # Get run record from the supabase table
            logging.info(f"Looking up agent_run with ID: {run_id}")
            result = self.supabase.table("agent_runs")\
                .select("*")\
                .eq("id", run_id)\
                .execute()

            if not result.data:
                logging.warning(f"No agent_run found with ID: {run_id}")
                raise HTTPException(status_code=404, detail="Run not found")

            logging.info(f"Found agent_run: {result.data[0].get('id')}")
            run_data = result.data[0]

            # Extract necessary fields from request data
            workflow_id = data.get("workflow_id", "unknown")
            callback_url = data.get("callback_url", "")
            reason = data.get("reason")

            # Initialize email_settings
            email_settings_data = None
            email_settings_obj = None

            # Try to get email_settings from request or agent_run
            if "email_settings" in data and data["email_settings"]:
                email_settings_data = data["email_settings"]
                # Convert to proper format
                try:
                    # Import locally to avoid scope issues
                    from models.human_in_the_loop import EmailSettings
                    email_settings_obj = EmailSettings(**email_settings_data)
                except Exception as e:
                    logging.warning(f"Could not parse email_settings from request: {str(e)}")
            elif run_data.get("email_settings"):
                email_settings_data = run_data.get("email_settings")
                try:
                    # Import locally to avoid scope issues
                    from models.human_in_the_loop import EmailSettings
                    email_settings_obj = EmailSettings(**email_settings_data)
                except Exception as e:
                    logging.warning(f"Could not parse email_settings from agent_run: {str(e)}")

            # Insert into human_in_the_loop table
            hitl_data = {
                "run_id": run_id,
                "email_settings": email_settings_data,
                "status": HumanFeedbackStatus.PENDING.value,
                "workflow_id": workflow_id,
                "reason": reason,
                "callback_url": callback_url
            }

            hitl_result = self.supabase.table("human_in_the_loop")\
                .insert(hitl_data)\
                .execute()

            if not hitl_result.data:
                raise HTTPException(status_code=500, detail="Failed to create human-in-the-loop request")

            hitl_record = hitl_result.data[0]
            hitl_id = hitl_record["id"]

            # Send email notification if email_settings are available
            if email_settings_data:
                logging.info(f"Found email_settings: {email_settings_data}")
                try:
                    # Manual extraction of email data if parsing to EmailSettings object failed
                    if not email_settings_obj:
                        # Try to manually extract recipient information
                        recipients = []
                        subject = "Review Request"

                        if isinstance(email_settings_data, dict):
                            subject = email_settings_data.get("subject", "Review Request")
                            raw_recipients = email_settings_data.get("recipients", [])

                            if isinstance(raw_recipients, list):
                                for recipient in raw_recipients:
                                    if isinstance(recipient, dict) and "email" in recipient:
                                        recipients.append({
                                            "email": recipient["email"],
                                            "name": recipient.get("name", recipient["email"])
                                        })

                        if recipients:
                            logging.info(f"Manually extracted {len(recipients)} recipients from email_settings")
                        else:
                            logging.warning("Could not extract any recipients from email_settings")
                            return HumanInTheLoop.model_validate(hitl_record)
                    else:
                        # Use the parsed object
                        subject = email_settings_obj.subject
                        recipients = [{"email": r.email, "name": r.name or r.email} for r in email_settings_obj.recipients]

                    # Send emails
                    email_service = EmailService()
                    frontend_url = os.getenv("FRONTEND_URL")
                    review_url = f"{frontend_url}/human-in-the-loop/{hitl_id}"

                    for recipient in recipients:
                        try:
                            await email_service.send_email(
                                template_name="interview-invitation",
                                to_email=recipient["email"],
                                subject_key="interview_invitation.subject",
                                locale="en",  # Default to English
                                interview_url=review_url,
                                recipient_name=recipient["name"] or recipient["email"],
                                reason=reason or "Workflow requires your review"
                            )

                            logging.info(f"Sent review request email to {recipient['email']} for HITL ID: {hitl_id}")
                        except Exception as e:
                            logging.error(f"Error sending email to {recipient['email']}: {str(e)}", exc_info=True)

                except Exception as e:
                    # Log the error but don't fail the request if email sending fails
                    logging.error(f"Error in email sending process: {str(e)}", exc_info=True)
            else:
                logging.info(f"No email_settings data for HITL ID: {hitl_id}, skipping email notification")

            # Return the created record
            return HumanInTheLoop.model_validate(hitl_record)

        except Exception as e:
            logging.error(f"Error requesting human feedback: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to request human feedback: {str(e)}"
            )
            
    async def update_human_feedback(self, hitl_id: UUID4, status: HumanFeedbackStatus, feedback: Optional[str] = None) -> HumanInTheLoop:
        """Update the status of a human-in-the-loop request and trigger the callback if needed"""
        try:
            # Get the HITL record
            result = self.supabase.table("human_in_the_loop")\
                .select("*")\
                .eq("id", str(hitl_id))\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Human-in-the-loop request not found")

            hitl_record = result.data[0]

            # Update the status
            update_data = {
                "status": status.value
            }

            # Add feedback as reason if provided
            if feedback:
                update_data["reason"] = feedback

            update_result = self.supabase.table("human_in_the_loop")\
                .update(update_data)\
                .eq("id", str(hitl_id))\
                .execute()

            if not update_result.data:
                raise HTTPException(status_code=500, detail="Failed to update human-in-the-loop request")

            updated_record = update_result.data[0]

            # If there's a callback URL, send the result to continue the workflow
            callback_url = hitl_record.get("callback_url")
            if callback_url:
                try:
                    async with httpx.AsyncClient() as client:
                        # Prepare the callback payload
                        payload = {
                            "hitl_id": str(hitl_id),
                            "status": status.value,
                            "feedback": feedback,
                            "workflow_id": hitl_record.get("workflow_id"),
                            "run_id": str(hitl_record.get("run_id"))
                        }

                        # Call the callback URL
                        response = await client.post(
                            callback_url,
                            json=payload,
                            timeout=10.0  # 10 second timeout
                        )

                        if response.status_code < 200 or response.status_code >= 300:
                            logging.warning(f"Callback to {callback_url} returned status {response.status_code}")

                        logging.info(f"Successfully sent callback for HITL ID: {hitl_id} with status: {status.value}")

                except Exception as e:
                    # Log the error but don't fail the request
                    logging.error(f"Error sending callback for HITL ID {hitl_id}: {str(e)}")

            return HumanInTheLoop.model_validate(updated_record)

        except Exception as e:
            logging.error(f"Error updating human feedback: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update human feedback: {str(e)}"
            )

    async def get_human_feedback(self, hitl_id: UUID4) -> HumanInTheLoop:
        """Get details of a human-in-the-loop request"""
        try:
            result = self.supabase.table("human_in_the_loop")\
                .select("*")\
                .eq("id", str(hitl_id))\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Human-in-the-loop request not found")

            return HumanInTheLoop.model_validate(result.data[0])

        except Exception as e:
            logging.error(f"Error getting human feedback: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get human feedback: {str(e)}"
            )

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

@router.get("/workflow/{run_id}/env")
async def get_workflow_env(run_id: str):
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
        # We'll handle the validation and extraction there
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
async def get_human_feedback(hitl_id: UUID4):
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

        service = OperationService()
        return await service.update_human_feedback(hitl_id, status, reason)
    except Exception as e:
        logging.error(f"Error updating human feedback: {str(e)}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )