# api/v1/build.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional, Union
import uuid
import os
import json
import httpx
import logging
from dependencies.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/build", tags=["build"])

# Define models
class Flow(BaseModel):
    name: str
    jsonBody: Optional[Dict[str, Any]] = None
    url: Optional[str] = None
    javascript: Optional[str] = None

    @field_validator('url', 'javascript')
    @classmethod
    def validate_flow_type(cls, v, info):
        # Check if both url and javascript are provided
        values = info.data
        if v is not None and 'url' in values and 'javascript' in values:
            if values['url'] is not None and values['javascript'] is not None:
                raise ValueError('Flow cannot have both url and javascript properties')
        return v

    @field_validator('jsonBody')
    @classmethod
    def validate_json_body(cls, v, info):
        # Check if url is provided without jsonBody
        values = info.data
        if 'url' in values and values['url'] is not None and v is None:
            raise ValueError('jsonBody is required when url is provided')
        return v

class Agent(BaseModel):
    name: str
    flows: List[Flow]

class BuildRequest(BaseModel):
    agent: Agent

# Template strings - hard-coded to avoid file system issues
WORKFLOW_TEMPLATE = """
{
  "name": "${{workfow-name}}",
  "nodes": [
${{generated-nodes}}
  ],
  "connections": ${{generated-connections}},
  "settings": {}
}
"""

WEBHOOK_TEMPLATE = """
{
  "id": "${{node-uuid}}",
  "name": "${{node-name}}",
  "webhookId": "${{webhook-uuid}}",
  "parameters": {
    "httpMethod": "POST",
    "path": "${{webhook-uuid}}",
    "responseMode": "responseNode",
    "options": {}
  },
  "type": "n8n-nodes-base.webhook",
  "typeVersion": 2,
  "position": [
    ${{position-x}},
    ${{position-y}}
  ]
}
"""

CODE_TEMPLATE = """
{
  "id": "${{node-uuid}}",
  "name": "${{node-name}}",
  "parameters": {
    "jsCode": "${{generated-code}}"
  },
  "type": "n8n-nodes-base.code",
  "typeVersion": 2,
  "position": [
    ${{position-x}},
    ${{position-y}}
  ]
}
"""

HTTP_TEMPLATE = """
{
  "id": "${{node-uuid}}",
  "name": "${{node-name}}",
  "parameters": {
    "url": "${{url}}",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        {}
      ]
    },
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": ${{json-body}},
    "options": {}
  },
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [
    ${{position-x}},
    ${{position-y}}
  ]
}
"""

def get_template(template_name: str) -> str:
    """Get template string based on name"""
    templates = {
        "workflow-body-agent.txt": WORKFLOW_TEMPLATE,
        "webhook-receiver.txt": WEBHOOK_TEMPLATE,
        "code.txt": CODE_TEMPLATE,
        "httprequest.txt": HTTP_TEMPLATE
    }

    if template_name not in templates:
        raise HTTPException(
            status_code=500, 
            detail=f"Template not found: {template_name}"
        )

    return templates[template_name]

def replace_placeholders(template: str, replacements: Dict[str, str]) -> str:
    """Replace placeholders in template"""
    result = template.strip()
    for key, value in replacements.items():
        placeholder = f"${{{{{key}}}}}"
        result = result.replace(placeholder, str(value))
    return result

# Workflow generation function
def generate_workflow(request: BuildRequest) -> Dict[str, Any]:
    """Generate a workflow from templates and request data"""
    try:
        # Get master template
        workflow_template = get_template("workflow-body-agent.txt")

        # Generate nodes
        nodes = []
        node_ids = []
        node_names = []

        # Starting position
        x_pos = 50
        y_pos = 100

        # First node is always a webhook receiver
        webhook_template = get_template("webhook-receiver.txt")
        webhook_id = str(uuid.uuid4())
        webhook_uuid = str(uuid.uuid4())
        webhook_name = "Webhook"
        webhook_replacements = {
            "node-uuid": webhook_id,
            "node-name": webhook_name,
            "webhook-uuid": webhook_uuid,
            "position-x": str(x_pos),
            "position-y": str(y_pos)
        }
        webhook_node_str = replace_placeholders(webhook_template, webhook_replacements)
        nodes.append(webhook_node_str)
        node_ids.append(webhook_id)
        node_names.append(webhook_name)

        # Increment X position for next node
        x_pos += 300

        # Generate nodes for each flow
        for i, flow in enumerate(request.agent.flows):
            if not flow.url and not flow.javascript:
                raise HTTPException(
                    status_code=400,
                    detail=f"Flow '{flow.name}' must have either url or javascript property"
                )

            if flow.url:
                # HTTP request node
                http_template = get_template("httprequest.txt")
                node_id = str(uuid.uuid4())
                node_name = flow.name
                replacements = {
                    "node-uuid": node_id,
                    "node-name": node_name,
                    "json-body": json.dumps(flow.jsonBody or {}),
                    "url": flow.url,
                    "position-x": str(x_pos),
                    "position-y": str(y_pos)
                }
                http_node_str = replace_placeholders(http_template, replacements)
                nodes.append(http_node_str)
                node_ids.append(node_id)
                node_names.append(node_name)

            elif flow.javascript:
                # Code node
                code_template = get_template("code.txt")
                node_id = str(uuid.uuid4())
                node_name = flow.name
                # Escape quotes in JavaScript code
                escaped_js = flow.javascript.replace('"', '\\"')
                replacements = {
                    "node-uuid": node_id,
                    "node-name": node_name,
                    "generated-code": escaped_js,
                    "position-x": str(x_pos),
                    "position-y": str(y_pos)
                }
                code_node_str = replace_placeholders(code_template, replacements)
                nodes.append(code_node_str)
                node_ids.append(node_id)
                node_names.append(node_name)

            # Increment X position for next node
            x_pos += 300

        # Generate connections - proper n8n format
        connections = {}

        for i in range(len(node_ids) - 1):
            source_id = node_ids[i]
            source_name = node_names[i]
            target_id = node_ids[i + 1]

            if source_name not in connections:
                connections[source_name] = {
                    "main": [
                        []  # Create first output
                    ]
                }

            # Add the connection with the correct index
            connections[source_name]["main"][0].append({
                "node": node_names[i + 1],  # Use name instead of ID
                "type": "main",
                "index": 0
            })

        # Join nodes with commas and proper indentation
        nodes_json = ",\n".join(nodes)

        # Replace placeholders in workflow template
        workflow_replacements = {
            "workfow-name": request.agent.name,
            "generated-nodes": nodes_json,
            "generated-connections": json.dumps(connections)
        }
        workflow_json_str = replace_placeholders(workflow_template, workflow_replacements)

        # Debug the generated JSON
        logger.debug(f"Generated workflow JSON: {workflow_json_str}")

        try:
            # Parse the resulting JSON
            parsed_json = json.loads(workflow_json_str)
            return parsed_json

        except json.JSONDecodeError as e:
            error_location = e.pos
            context_start = max(0, error_location - 100)
            context_end = min(len(workflow_json_str), error_location + 100)
            error_context = workflow_json_str[context_start:context_end]

            raise HTTPException(
                status_code=500,
                detail=f"Invalid workflow JSON: {str(e)}. Error near: {error_context}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate workflow: {str(e)}")

@router.post("")
async def build_workflow(request: BuildRequest, user_id: uuid.UUID = Depends(get_current_user)):
    """
    Creates an n8n workflow from the provided agent configuration and
    uploads it to the n8n instance.
    """
    return await _build_workflow(request, user_id)

@router.post("/workflow")
async def build_workflow_alternate(request: BuildRequest, user_id: uuid.UUID = Depends(get_current_user)):
    """
    Alternative endpoint with /workflow path to maintain backward compatibility.
    Creates an n8n workflow from the provided agent configuration and
    uploads it to the n8n instance.
    """
    return await _build_workflow(request, user_id)

async def _build_workflow(request: BuildRequest, user_id: uuid.UUID):
    """
    Implementation of workflow building functionality.

    The workflow is built by combining template nodes based on the flows defined 
    in the request, with each flow becoming either a code or HTTP request node.
    """
    try:
        # Generate workflow JSON
        workflow_json = generate_workflow(request)

        # Send to n8n API
        n8n_url = os.getenv("N8N_URL")
        n8n_api_key = os.getenv("N8N_API_KEY")

        if not n8n_url or not n8n_api_key:
            raise HTTPException(status_code=500, detail="N8N_URL or N8N_API_KEY environment variables not set")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{n8n_url}/api/v1/workflows",
                json=workflow_json,
                headers={
                    "X-N8N-API-KEY": n8n_api_key,
                    "Content-Type": "application/json"
                }
            )

            if response.status_code >= 400:
                logger.error(f"N8n API error: {response.status_code}, {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"N8n API error: {response.text}"
                )

            return response.json()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to build workflow: {str(e)}")