import os
import json
import httpx
import logging
from datetime import datetime, timezone
from fastapi import HTTPException
from typing import Dict, Any, List, Optional
from pydantic import UUID4
from models.operation import Operation, OperationCreate, TeamStatus, AgentStatus
from models.human_in_the_loop import HumanInTheLoop, HumanInTheLoopCreate, HumanFeedbackStatus, EmailSettings
from services.email import EmailService
from supabase import create_client
from services.agents import AgentService  
import asyncio

logger = logging.getLogger(__name__)

class OperationService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        
        ngina_url = os.getenv("NGINA_URL", "http://localhost:8000")
        self.api_base_url = ngina_url + "/api/v1"
        self.ngina_url = ngina_url
        self.ngina_accounting_key = os.getenv("NGINA_ACCOUNTING_KEY")
        self.ngina_workflow_key = os.getenv("NGINA_WORKFLOW_KEY")
        self.ngina_scratchpad_key = os.getenv("NGINA_SCRATCHPAD_KEY")
        self.n8n_url = os.getenv("N8N_URL")
        self.n8n_api_key = os.getenv("N8N_API_KEY")

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

    async def create_n8n_workflow(self, agent_name: str) -> Dict[str, Any]:
        """Create a new workflow instance in n8n"""
        try:
            # Check if n8n environment variables are set
            if not self.n8n_url or not self.n8n_api_key:
                raise HTTPException(
                    status_code=500, 
                    detail="N8N_URL or N8N_API_KEY environment variables not set"
                )

            # Load the workflow template
            template_path = os.path.join("n8n/flow-templates", "chain.json")
            logging.info(f"Loading workflow template from: {template_path}")

            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    workflow_template = f.read()
            except FileNotFoundError:
                logging.error(f"Workflow template not found at {template_path}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"Workflow template not found at {template_path}"
                )

            # Generate a new UUID for the webhook_id
            import uuid
            webhook_id = str(uuid.uuid4())

            # Replace variables in the template
            flow_name = f"Run of {agent_name}"
            workflow_content = workflow_template.replace("${{flow-name}}", flow_name)
            workflow_content = workflow_content.replace("${{ngina_backend_url}}", self.api_base_url or "")
            # Make sure to enclose webhook_id in double curly braces for replacement
            workflow_content = workflow_content.replace("${{webhook_id}}", webhook_id)
            

            logging.info(f"Webhook ID generated for workflow: {webhook_id}")

            # Parse the workflow content to JSON
            try:
                workflow_json = json.loads(workflow_content)
            except json.JSONDecodeError as e:
                logging.error(f"Error parsing workflow template: {str(e)}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"Error parsing workflow template: {str(e)}"
                )

            # Send to n8n API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.n8n_url}/api/v1/workflows",
                    json=workflow_json,
                    headers={
                        "X-N8N-API-KEY": self.n8n_api_key,
                        "Content-Type": "application/json"
                    }
                )

            if response.status_code != 200:
                logging.error(f"Error creating workflow in n8n: {response.text}")
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"Error creating workflow in n8n: {response.text}"
                )

            # Parse the response
            response_json = response.json()

            # Find the webhook node and extract the path
            webhook_path = None
            for node in response_json.get("nodes", []):
                if node.get("name") == "run-description":
                    webhook_path = node.get("parameters", {}).get("path")
                    if not webhook_path and webhook_id:
                        # If webhook_path is still using the variable, use our generated ID
                        webhook_path = webhook_id
                    break

            if not webhook_path:
                logging.error("Failed to extract webhook path from n8n response, using generated ID")
                webhook_path = webhook_id

            # Log the complete response for debugging
            logging.debug(f"Complete n8n workflow creation response: {response_json}")

            # Return the created workflow information
            return {
                "workflow_id": response_json.get("id"),
                "name": response_json.get("name"),
                "agent_endpoint": webhook_path, # Keep this for backward compatibility
                "webhook_path": webhook_path,
                "webhook_id": webhook_id
            }

        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logging.error(f"Error creating n8n workflow: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to create n8n workflow: {str(e)}"
            )

    async def activate_workflow(self, n8n_workflow_id: str, is_active: bool = True) -> Dict[str, Any]:
        """Activate or deactivate an n8n workflow"""
        try:
            # Check if n8n environment variables are set
            if not self.n8n_url or not self.n8n_api_key:
                raise HTTPException(
                    status_code=500, 
                    detail="N8N_URL or N8N_API_KEY environment variables not set"
                )

            # Determine the endpoint based on whether we're activating or deactivating
            endpoint = "activate" if is_active else "deactivate"
            url = f"{self.n8n_url}/api/v1/workflows/{n8n_workflow_id}/{endpoint}"

            logging.info(f"{'Activating' if is_active else 'Deactivating'} workflow: {n8n_workflow_id}")

            # Send request to n8n API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={
                        "X-N8N-API-KEY": self.n8n_api_key,
                        "Content-Type": "application/json"
                    },
                    timeout=10.0  # Add a timeout to prevent hanging
                )

            # Check response status
            if response.status_code != 200:
                logging.error(f"Error {'activating' if is_active else 'deactivating'} workflow: {response.text}")
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"Error {'activating' if is_active else 'deactivating'} workflow: {response.text}"
                )

            # Parse the response
            response_json = response.json()

            # Check if the activation/deactivation was successful
            # Some n8n versions have different response formats, so try to handle that
            if "active" in response_json and response_json.get("active") != is_active:
                logging.error(f"Failed to {'activate' if is_active else 'deactivate'} workflow: {response_json}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to {'activate' if is_active else 'deactivate'} workflow"
                )

            logging.info(f"Successfully {'activated' if is_active else 'deactivated'} workflow: {n8n_workflow_id}")

            return response_json

        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logging.error(f"Error {'activating' if is_active else 'deactivating'} workflow: {str(e)}", exc_info=True)
            # Don't raise an exception here, just return a status
            return {
                "success": False,
                "error": str(e),
                "workflow_id": n8n_workflow_id
            }

    async def get_operation_by_run_id(self, run_id: str) -> Operation:
        """
        Get an operation by its run_id
        """
        try:
            result = self.supabase.table("agent_runs")\
                .select("*")\
                .eq("id", run_id)\
                .execute()

            if not result.data:
                return None

            return Operation.model_validate(result.data[0])

        except Exception as e:
            logging.error(f"Error getting operation by run_id: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get operation by run_id: {str(e)}")
            
    async def create_or_update_operation(self, operation_data: dict) -> Operation:
        try:
            agent_endpoint_url = None  # Initialize this to track the agent endpoint URL

            # If agent_id is provided, get the agent details
            if operation_data.get("agent_id"):
                # Get agent details - make sure this is properly awaited
                agent_result = self.supabase.table("agents")\
                    .select("*")\
                    .eq("id", operation_data["agent_id"])\
                    .execute()

                if not agent_result.data:
                    logging.warning(f"Agent with ID {operation_data['agent_id']} not found")
                else:
                    agent = agent_result.data[0]
                    agent_name = agent.get("title", {}).get("en", "Untitled Agent")
                    agent_endpoint_url = agent.get("agent_endpoint", "")  # Store the endpoint URL
                    agent_webhook_url = agent.get("workflow_webhook_url", "")
                    webhook_url = None

                    # Check if the agent already has a workflow_id
                    existing_workflow_id = agent.get("workflow_id")
                    logger.info("Existing workflow ID: %s", existing_workflow_id)
                    if not existing_workflow_id:
                        # Create a new workflow in n8n only if the agent doesn't have a workflow_id
                        try:
                            # Make sure this is properly awaited
                            workflow_info = await self.create_n8n_workflow(agent_name)

                            # Get the n8n workflow ID from the response
                            n8n_workflow_id = workflow_info["workflow_id"]

                            # Add workflow information to operation data
                            operation_data["workflow_id"] = n8n_workflow_id

                            # Create the webhook URL using webhook_id
                            webhook_url = f"{self.n8n_url}/webhook/{workflow_info['webhook_id']}"

                            # Update the agent's workflow_id field with the n8n workflow ID
                            try:
                                # Make sure this is properly awaited
                                agent_update_result = self.supabase.table("agents")\
                                    .update({"workflow_id": n8n_workflow_id,
                                             "workflow_webhook_url": webhook_url })\
                                    .eq("id", operation_data["agent_id"])\
                                    .execute()

                                if agent_update_result.data:
                                    logging.info(f"Updated agent {operation_data['agent_id']} with workflow ID: {n8n_workflow_id}")

                                    # Activate the workflow after updating the agent
                                    try:
                                        # Make sure this is properly awaited
                                        activation_result = await self.activate_workflow(n8n_workflow_id, True)
                                        logging.info(f"Workflow activation result: {activation_result}")
                                    except Exception as activation_error:
                                        logging.error(f"Error activating workflow: {str(activation_error)}")
                                        # Continue even if activation fails
                                else:
                                    logging.warning(f"Failed to update agent {operation_data['agent_id']} with workflow ID")
                            except Exception as e:
                                logging.error(f"Error updating agent with workflow ID: {str(e)}")
                                # Continue with operation creation even if agent update fails

                            logging.info(f"Created workflow for agent {agent_name}: {workflow_info}")
                        except Exception as e:
                            logging.error(f"Error creating workflow: {str(e)}")
                            # Continue without workflow if creation fails
                    else:
                        # Use the existing workflow ID
                        logging.info(f"Agent {operation_data['agent_id']} already has workflow ID: {existing_workflow_id}")
                        operation_data["workflow_id"] = existing_workflow_id

                        # use agent_endpoint_url
                        webhook_url = agent_webhook_url

            # Always create a new operation record for each run
            result = self.supabase.table("agent_runs")\
                .insert(operation_data)\
                .execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="Failed to create operation record")

            # Get the saved operation with the assigned ID
            saved_operation = result.data[0]
            run_id = str(saved_operation["id"])
            logging.info(f"New operation created with ID: {run_id}")

            # Now trigger the webhook if needed
            if webhook_url:
                # Prepare payload with initial parameters
                payload = None
                if operation_data.get("agent_id") and operation_data.get("results") and operation_data["results"].get("inputParameters"):
                    payload = {
                        "run_id": run_id,  # Use the ID from the saved operation
                        "agents": [
                            {
                                "id": operation_data["agent_id"],
                                "url": agent_endpoint_url or "",  # Use the stored endpoint URL
                                "input": operation_data["results"]["inputParameters"]
                            }
                        ]
                    }
                    logging.info(f"Prepared webhook payload: {payload}")
                else:
                    logging.warning("Missing required data for webhook payload")
                    # Create a minimal payload with just the run_id
                    payload = {
                        "run_id": run_id,
                        "agents": []
                    }

                # Make sure this is properly awaited or handled if we don't want to wait
                await self.trigger_workflow_webhook(webhook_url, payload)

            return Operation.model_validate(saved_operation)

        except Exception as e:
            logging.error(f"Error creating/updating operation: {str(e)}", exc_info=True)
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

    async def delete_operation(self, operation_id: UUID4) -> bool:
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

    async def get_human_feedback_by_run(self, run_id: UUID4 = None, status: str = None):
         """
         Get human-in-the-loop feedback requests filtered by run_id and status

         Args:
             run_id: Optional run ID to filter requests for a specific run
             status: Optional status to filter requests (e.g., 'pending', 'approved', 'rejected')

         Returns:
             List of HumanInTheLoop objects matching the filters
         """
         try:
             # Start with the basic query using Supabase
             query = self.supabase.table("human_in_the_loop").select("*")

             # Add filters if provided
             if run_id:
                 query = query.eq("run_id", str(run_id))

             if status:
                 query = query.eq("status", status)

             # Order by creation date, most recent first
             query = query.order("created_at", desc=True)

             # Execute the query
             result = query.execute()

             if not result.data:
                 return []

             # Return the results directly - they're already in the right format
             return result.data

         except Exception as e:
             logging.error(f"Error fetching human feedback requests: {str(e)}", exc_info=True)
             raise
             
    async def process_workflow_results(self, run_id: str, agent_id: str, result_data: Any, x_ngina_key: Optional[str] = None):
        """Process workflow results and store them using the scratchpads service"""
        try:
            # Validate API key
            if x_ngina_key != self.ngina_workflow_key:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid API key"
                )

            # Verify that the operation exists
            operation = await self.get_operation_by_run_id(run_id)
            if not operation:
                raise HTTPException(
                    status_code=404,
                    detail=f"Operation with run_id '{run_id}' not found"
                )

            # Get agent details to retrieve credits_per_run
            agent_service = AgentService()
            try:
                agent = await agent_service.get_agent(agent_id)

                # Asynchronously charge the user for agent execution without awaiting the result
                if agent.credits_per_run and agent.credits_per_run > 0:
                    asyncio.create_task(self._charge_user_for_agent(
                        user_id=operation.user_id,
                        agent_id=agent_id,
                        agent_title=agent.title.en if agent.title and agent.title.en else f"Agent {agent_id}",
                        credits=agent.credits_per_run,
                        run_id=run_id
                    ))
                    logging.info(f"Initiated async credit charge of {agent.credits_per_run} for user {operation.user_id}, run_id {run_id}")
            except Exception as e:
                # Log the error but continue processing the results
                logging.error(f"Error fetching agent or charging credits: {str(e)}")

            # Process and store the results
            # Get the user_id associated with this run
            user_id =  str(operation.user_id)

            if not user_id:
                raise HTTPException(
                    status_code=400,
                    detail="No user associated with this run"
                )

            # Use httpx to call the scratchpads endpoint
            async with httpx.AsyncClient() as client:
              

                # Use the user's ID instead of a system ID
                base_url = f"{self.ngina_url}/api/v1/scratchpads/{user_id}/{run_id}/{agent_id}/json"

                # Log request details for debugging
                logging.info(f"Base scratchpad URL: {base_url} for user_id: {user_id}")

                # Send the JSON data directly, not as a file
                response = await client.post(
                    base_url, 
                    json=result_data,  # Send as JSON payload directly
                    headers={
                        "x-ngina-key": self.ngina_scratchpad_key
                    }
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
                find_url_properties(result_data)

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
                            headers={
                                "x-ngina-key": self.ngina_scratchpad_key
                            }
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

                # Update results json
                try:
                    logger.info("*********** Updating RUN NOW *************")
                    # First, get the current record to check the existing results field
                    current_record = self.supabase.table("agent_runs")\
                        .select("results")\
                        .eq("id", run_id)\
                        .execute()

                    if not current_record.data:
                        logging.error(f"Could not find agent_run record with id {run_id} to update results")
                        raise HTTPException(
                            status_code=404,
                            detail=f"Agent run with id {run_id} not found"
                        )

                    # Get the current results field
                    current_results = current_record.data[0].get("results", {})

                    # Extract the resultJson from result_data
                    new_result = {
                       "executionId":  result_data.get("executionId", ""),
                       "agentId": result_data.get("agentId", ""),
                       "resultJson":  result_data.get("resultJson", {})
                    }

                    # If results is null or empty dict, initialize it
                    if not current_results:
                        updated_results = {"flow": [new_result]}
                    else:
                        # If flow array doesn't exist yet, create it
                        if "flow" not in current_results:
                            current_results["flow"] = []

                        # Append the new result to the flow array
                        current_results["flow"].append(new_result)
                        updated_results = current_results

                    # Update the record with the new results
                    update_result = self.supabase.table("agent_runs")\
                        .update({"results": updated_results})\
                        .eq("id", run_id)\
                        .execute()

                    if not update_result.data:
                        logging.error(f"Failed to update results for agent_run {run_id}")
                        raise HTTPException(
                            status_code=500,
                            detail="Failed to update agent run results"
                        )

                    logging.info(f"Successfully updated results for agent_run {run_id} with {new_result}")

                except Exception as e:
                    logging.error(f"Error updating agent run results: {str(e)}", exc_info=True)
                    # Don't throw an exception here, as we want to continue with the rest of the function
                    # Just log the error
                
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

    async def _charge_user_for_agent(self, user_id: UUID4, agent_id: str, agent_title: str, credits: int, run_id: str):
        """Helper method to charge user credits for agent execution"""
        try:
            # Prepare the charge request
            charge_data = {
                "credits": credits,
                "description": f"Agent execution: {agent_title}",
                "agent_id": agent_id,
                "run_id": run_id               
            }

            # Call the accounting service to charge the user
            async with httpx.AsyncClient() as client:
                accounting_url = f"{self.api_base_url}/accounting/charge/{user_id}"
                headers = {
                    "Content-Type": "application/json",
                    "X-Ngina-Key": self.ngina_accounting_key
                }

                response = await client.post(
                    accounting_url,
                    json=charge_data,
                    headers=headers,
                    timeout=10.0  # Set a reasonable timeout
                )

                # Log the result but don't wait for it
                if response.status_code == 200:
                    logging.info(f"Successfully charged {credits} credits to user {user_id} for agent {agent_id}")
                else:
                    logging.error(f"Failed to charge user {user_id}: {response.status_code} - {response.text}")

        except Exception as e:
            # Just log the error, don't raise an exception since this is an async task
            logging.error(f"Error charging user {user_id} for agent {agent_id}: {str(e)}")
            
    async def trigger_workflow_webhook(self, webhook_url: str, payload: Dict[str, Any] = None) -> None:
        """Trigger a workflow webhook without waiting for the response"""
        try:
            if not webhook_url:
                logging.error("Cannot trigger workflow: webhook URL is empty")
                return

            logging.info(f"Triggering workflow webhook asynchronously: {webhook_url}")

            # Use a default payload if none is provided
            if payload is None:
                payload = {
                    "trigger": "automation",
                    "timestamp": datetime.now().isoformat()
                }

            # Create a task to call the webhook without waiting for it to complete
            async def call_webhook():
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            webhook_url,
                            json=payload,
                            timeout=5.0  # Short timeout since we don't care about the response
                        )
                        logging.info(f"Webhook trigger sent to {webhook_url}, status: {response.status_code}")
                except Exception as e:
                    logging.error(f"Error triggering webhook {webhook_url}: {str(e)}")

            # Start the task without awaiting it
            import asyncio
            asyncio.create_task(call_webhook())

            logging.info(f"Webhook trigger task created for {webhook_url}")
        except Exception as e:
            logging.error(f"Error setting up webhook trigger: {str(e)}")
            # We don't want to raise an exception here as this is a fire-and-forget operation

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

    async def update_human_feedback(self, hitl_id: UUID4, status: HumanFeedbackStatus, reason: Optional[str] = None) -> HumanInTheLoop:
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
            if reason:
                update_data["reason"] = reason

            update_result = self.supabase.table("human_in_the_loop")\
                .update(update_data)\
                .eq("id", str(hitl_id))\
                .execute()

            if not update_result.data:
                raise HTTPException(status_code=500, detail="Failed to update human-in-the-loop request")

            updated_record = update_result.data[0]

            # If there's a callback URL and status is APPROVED, send the result to continue the workflow
            original_callback_url = hitl_record.get("callback_url")
            if original_callback_url and status == HumanFeedbackStatus.APPROVED:
                try:
                    # Replace protocol, host, and port with N8N_URL environment variable
                    n8n_base_url = os.getenv("N8N_URL")

                    if not n8n_base_url:
                        logging.warning("N8N_URL environment variable not set, using original callback URL")
                        callback_url = original_callback_url
                    else:
                        # Parse the original URL to get the path
                        from urllib.parse import urlparse, urljoin
                        parsed_url = urlparse(original_callback_url)
                        path = parsed_url.path

                        # Join the N8N base URL with the path
                        callback_url = urljoin(n8n_base_url, path)
                        logging.info(f"Replaced callback URL: {original_callback_url} -> {callback_url}")

                    async with httpx.AsyncClient() as client:
                        # Prepare the callback payload with approvalMessage
                        payload = {
                            "approvalMessage": reason or ""
                        }

                        logging.info(f"Sending callback to n8n at {callback_url}")

                        # Call the callback URL
                        response = await client.post(
                            callback_url,
                            json=payload,
                            timeout=10.0  # 10 second timeout
                        )

                        if response.status_code >= 200 and response.status_code < 300:
                            logging.info(f"Continuing workflow in n8n (POST to wait webhook was successful)")
                        else:
                            logging.info(f"Continuing workflow in n8n (POST to wait webhook failed with status {response.status_code})")
                            logging.warning(f"Callback to {callback_url} returned status {response.status_code}")

                except Exception as e:
                    # Log the error but don't fail the request
                    logging.info(f"Continuing workflow in n8n (POST to wait webhook failed: {str(e)})")
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

    async def get_agent_run_history(self, agent_id: UUID4, user_id: UUID4) -> List[Operation]:
        """
        Get the 50 most recent operations for a specific agent that belong to the given user

        Args:
            agent_id: ID of the agent to get history for
            user_id: ID of the user who should own these operations

        Returns:
            List of Operation objects matching the criteria
        """
        try:
            result = self.supabase.table("agent_runs")\
                .select("*")\
                .eq("agent_id", str(agent_id))\
                .eq("user_id", str(user_id))\
                .order("created_at", desc=True)\
                .limit(50)\
                .execute()

            if not result.data:
                return []

            return [Operation.model_validate(operation) for operation in result.data]

        except Exception as e:
            logging.error(f"Error getting agent run history: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get agent run history: {str(e)}")
 
    async def update_operation_status(self, run_id: str, status: str, debug_info: Dict[str, Any], api_key: str) -> Dict[str, Any]:
        """Update the status of an operation with debug information"""
        try:
            # Verify API key
            if api_key != self.ngina_workflow_key:
                raise HTTPException(
                    status_code=401, 
                    detail="Invalid API key"
                )

            # Check if run_id is in UUIDv4 format
            import re
            uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)

            original_id = run_id

            if not uuid_pattern.match(run_id):
                # Not a UUID, treat as an n8n operation_id
                logging.info(f"ID {run_id} is not a UUID, treating as n8n operation_id")

                if not self.n8n_url or not self.n8n_api_key:
                    raise HTTPException(
                        status_code=500, 
                        detail="N8N_URL or N8N_API_KEY environment variables not set"
                    )

                # Fetch execution data from n8n
                try:
                    async with httpx.AsyncClient() as client:
                        n8n_url = f"{self.n8n_url}/api/v1/executions/{run_id}?includeData=true"
                        logging.info(f"Fetching execution data from n8n at: {n8n_url}")

                        response = await client.get(
                            n8n_url,
                            headers={
                                "X-N8N-API-KEY": self.n8n_api_key,
                                "Content-Type": "application/json"
                            },
                            timeout=30.0  # Increase timeout for larger responses
                        )

                        if response.status_code != 200:
                            logging.error(f"Failed to fetch execution data from n8n: {response.status_code}")
                            raise HTTPException(
                                status_code=500,
                                detail=f"Failed to fetch execution data from n8n: {response.status_code}"
                            )

                        execution_data_json = response.json()
                        logging.info(f"Successfully fetched execution data for operation_id: {run_id}")

                        # Try approach 1: Follow JSON hierarchy
                        try:
                            run_id = execution_data_json["data"]["resultData"]["runData"]["run-description"][0]["data"]["main"][0][0]["json"]["body"]["run_id"]
                            logging.info(f"Found run_id using approach 1: {run_id}")
                        except (KeyError, IndexError, TypeError) as e:
                            logging.warning(f"Could not extract run_id using approach 1: {str(e)}")
                            run_id = None

                        # If approach 1 fails, try approach 2: Search for run_id attribute
                        if not run_id:
                            logging.info("Attempting approach 2: Searching for run_id in JSON")

                            def find_run_id(obj):
                                """Recursively search for run_id in nested dictionaries"""
                                if isinstance(obj, dict):
                                    if "run_id" in obj:
                                        return obj["run_id"]

                                    for key, value in obj.items():
                                        result = find_run_id(value)
                                        if result:
                                            return result
                                elif isinstance(obj, list):
                                    for item in obj:
                                        result = find_run_id(item)
                                        if result:
                                            return result

                                return None

                            run_id = find_run_id(execution_data_json)

                            if run_id:
                                logging.info(f"Found run_id using approach 2: {run_id}")
                            else:
                                logging.error("Failed to find run_id in execution data")
                                raise HTTPException(
                                    status_code=500, 
                                    detail="Could not find run_id in n8n execution data"
                                )

                        # Validate that the found run_id is a valid UUID
                        if not uuid_pattern.match(run_id):
                            logging.error(f"Found run_id {run_id} is not a valid UUID")
                            raise HTTPException(
                                status_code=500,
                                detail=f"Found run_id {run_id} is not a valid UUID"
                            )

                except Exception as e:
                    if isinstance(e, HTTPException):
                        raise e
                    logging.error(f"Error fetching execution data from n8n: {str(e)}", exc_info=True)
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error fetching execution data from n8n: {str(e)}"
                    )

            # Get the current timestamp for finished_at
            now = datetime.now(timezone.utc).isoformat()

            # Update the agent_runs table with status, finished_at and results
            update_data = {
                "status": status,
                "finished_at": now
            }

            # Update the record in the database
            result = self.supabase.table("agent_runs")\
                .update(update_data)\
                .eq("id", run_id)\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Operation not found")

            updated_record = result.data[0]

            # Log successful update
            logging.info(f"Successfully updated operation status for run_id: {run_id} to {status}")

            return {
                "message": "Operation status updated successfully",
                "run_id": run_id,
                "original_id": original_id if original_id != run_id else None,
                "status": status,
                "finished_at": now
            }

        except Exception as e:
            logging.error(f"Error updating operation status: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update operation status: {str(e)}"
            )