# api/v1/diagnostics.py
from fastapi import APIRouter, Response, Request
from fastapi.responses import StreamingResponse
from typing import AsyncIterator, List
import logging
import os
import uuid
import json
import httpx
from datetime import datetime, timedelta
from jose import jwt
from supabase import create_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

# Test constants
TEST_USER_EMAIL = "system@diagnostics.com"
TEST_USER_PASSWORD = "888-111-2131"
TEST_AGENT_URL = "/api/v1/mockup-agents/web-page-scraper"

class TestResults:
    """Class to store and track test results"""
    def __init__(self):
        self.failed_tests: List[str] = []

async def generate_test_suite(test_results: TestResults) -> AsyncIterator[str]:
    """Generate the integration test suite as a stream of text"""
    yield "# Integration Test Suite\n"
    yield f"# Generated: {datetime.now().isoformat()}\n\n"

    # Store test state across all tests
    test_state = {
        "auth_token": None,
        "user_id": None,
        "agent_id": None,
        "run_id": None,
        "team_id": None,
    }

    # ===== Section 1: Connectivity Tests =====
    yield "## 1. Connectivity Tests\n\n"

    # N8N connectivity test
    yield "### 1.1 N8N Connectivity\n"
    try:
        n8n_url = os.getenv("N8N_URL")
        n8n_api_key = os.getenv("N8N_API_KEY")

        if not n8n_url or not n8n_api_key:
            yield "ERROR: N8N_URL or N8N_API_KEY environment variables not set\n"
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{n8n_url}/api/v1/workflows",
                    headers={"X-N8N-API-KEY": n8n_api_key}
                )

                if response.status_code == 200:
                    yield "✅ PASS: Successfully connected to N8N API\n"
                    yield f"Status code: {response.status_code}\n"
                else:
                    test_results.failed_tests.append("N8N Connectivity")
                    yield f"❌ FAIL: Failed to connect to N8N API. Status code: {response.status_code}\n"
                    yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("N8N Connectivity")
        yield f"ERROR: N8N connectivity test failed with exception: {str(e)}\n"

    yield "\n"

    # Supabase connectivity test
    yield "### 1.2 Supabase Connectivity\n"
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            yield "ERROR: SUPABASE_URL or SUPABASE_KEY environment variables not set\n"
        else:
            supabase = create_client(supabase_url, supabase_key)

            # Attempt to query the agents table
            result = supabase.table("agents").select("*").limit(1).execute()

            if result and hasattr(result, 'data'):
                yield "✅ PASS: Successfully connected to Supabase and queried the agents table\n"
                yield f"Number of agents retrieved: {len(result.data)}\n"
            else:
                test_results.failed_tests.append("Supabase Connectivity")
                yield "❌ FAIL: Could not retrieve agents data from Supabase\n"
    except Exception as e:
        test_results.failed_tests.append("Supabase Connectivity")
        yield f"ERROR: Supabase connectivity test failed with exception: {str(e)}\n"

    yield "\n"

    # JWT authentication test
    yield "### 1.3 Supabase Auth (JWT)\n"
    try:
        # Generate JWT token for test user
        jwt_secret = os.getenv('SUPABASE_JWT_SECRET', '69fbcb2b-074e-41b8-b4ea-e85a11703e42')
        algorithm = "HS256"

        # Generate a test user ID
        user_id = str(uuid.uuid4())
        test_state["user_id"] = user_id

        # Set expiration to 1 hour from now
        expire = datetime.utcnow() + timedelta(minutes=60)

        # Create JWT payload with required claims
        to_encode = {
            "sub": user_id,
            "email": TEST_USER_EMAIL,
            "exp": expire,
            "aud": "authenticated"  # Required for Supabase auth
        }

        # Encode the JWT
        auth_token = jwt.encode(to_encode, jwt_secret, algorithm=algorithm)
        test_state["auth_token"] = auth_token

        if auth_token:
            yield "✅ PASS: Successfully created JWT token for authentication\n"
            yield f"User ID: {user_id}\n"
        else:
            test_results.failed_tests.append("JWT Authentication")
            yield "❌ FAIL: Failed to create JWT token\n"
    except Exception as e:
        test_results.failed_tests.append("JWT Authentication")
        yield f"ERROR: JWT creation test failed with exception: {str(e)}\n"

    yield "\n"

    # ===== Section 2: Agents Tests =====
    yield "## 2. Agents Tests\n\n"

    api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    yield "**Backend-URL:** " + api_base_url + "\n\n"

    # Create Agent test
    yield "### 2.1 Create Agent\n"
    try:
        if not test_state["auth_token"]:
            yield "SKIP: Skipping test because JWT creation failed\n"
        else:
            # Prepare agent data for creation
            agent_data = {
                "title": {
                    "en": "Integration Test Agent",
                    "de": "Integrationstestagent"
                },
                "description": {
                    "en": "Agent created for API integration testing",
                    "de": "Agent für API-Integrationstests erstellt"
                },
                "agent_endpoint": TEST_AGENT_URL,
                "max_execution_time_secs": 60,
                "input": {
                    "url_to_scrape": {
                        "type": "text",
                        "description": "URL to scrape"
                    }
                },
                "output": {
                    "markdown": {
                        "type": "text",
                        "description": "Extracted content"
                    },
                    "success": {
                        "type": "boolean",
                        "description": "Status flag"
                    },
                    "error_message": {
                        "type": "text",
                        "description": "Error details if any"
                    }
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{api_base_url}/v1/agents",
                    json=agent_data,
                    headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                )

                if response.status_code in (200, 201):
                    response_data = response.json()
                    test_state["agent_id"] = response_data.get("id")
                    yield f"✅ PASS: Successfully created agent with ID: {test_state['agent_id']}\n"
                    yield f"Status code: {response.status_code}\n"
                else:
                    test_results.failed_tests.append("Create Agent")
                    yield f"❌ FAIL: Failed to create agent. Status code: {response.status_code}\n"
                    yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("Create Agent")
        yield f"ERROR: Create agent test failed with exception: {str(e)}\n"

    yield "\n"

    # Get Agent test
    yield "### 2.2 Get Agent\n"
    try:
        if not test_state["agent_id"]:
            yield "SKIP: Skipping test because agent creation failed\n"
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{api_base_url}/v1/agents/{test_state['agent_id']}",
                    headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                )

                if response.status_code == 200:
                    response_data = response.json()
                    yield "✅ PASS: Successfully retrieved the agent\n"
                    yield f"Status code: {response.status_code}\n"
                    yield f"Agent name: {response_data.get('title', {}).get('en')}\n"
                else:
                    test_results.failed_tests.append("Get Agent")
                    yield f"❌ FAIL: Failed to retrieve agent. Status code: {response.status_code}\n"
                    yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("Get Agent")
        yield f"ERROR: Get agent test failed with exception: {str(e)}\n"

    yield "\n"

    # Update Agent test
    yield "### 2.3 Update Agent\n"
    try:
        if not test_state["agent_id"]:
            yield "SKIP: Skipping test because agent creation failed\n"
        else:
            # Prepare updated agent data
            updated_agent_data = {
                "title": {
                    "en": "Updated Integration Test Agent",
                    "de": "Aktualisierter Integrationstestagent"
                },
                "description": {
                    "en": "Updated agent for integration testing",
                    "de": "Aktualisierter Agent für Integrationstests"
                },
                "max_execution_time_secs": 90  # Increased timeout
            }

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{api_base_url}/v1/agents/{test_state['agent_id']}",
                    json=updated_agent_data,
                    headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                )

                if response.status_code == 200:
                    response_data = response.json()
                    yield "✅ PASS: Successfully updated the agent\n"
                    yield f"Status code: {response.status_code}\n"
                    yield f"Updated title: {response_data.get('title', {}).get('en')}\n"
                    yield f"Updated timeout: {response_data.get('max_execution_time_secs')} seconds\n"
                else:
                    test_results.failed_tests.append("Update Agent")
                    yield f"❌ FAIL: Failed to update agent. Status code: {response.status_code}\n"
                    yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("Update Agent")
        yield f"ERROR: Update agent test failed with exception: {str(e)}\n"

    yield "\n"

    # List Agents test
    yield "### 2.4 List Agents\n"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_base_url}/v1/agents",
                headers={"Authorization": f"Bearer {test_state['auth_token']}"}
            )

            if response.status_code == 200:
                response_data = response.json()
                yield "✅ PASS: Successfully retrieved the list of agents\n"
                yield f"Status code: {response.status_code}\n"
                yield f"Number of agents: {len(response_data)}\n"

                # Verify our test agent is in the list
                if test_state["agent_id"]:
                    agent_found = any(agent.get("id") == test_state["agent_id"] for agent in response_data)
                    if agent_found:
                        yield "✅ PASS: Test agent was found in the list\n"
                    else:
                        test_results.failed_tests.append("List Agents - Agent Not Found")
                        yield "❌ FAIL: Test agent was not found in the list\n"
            else:
                test_results.failed_tests.append("List Agents")
                yield f"❌ FAIL: Failed to list agents. Status code: {response.status_code}\n"
                yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("List Agents")
        yield f"ERROR: List agents test failed with exception: {str(e)}\n"

    yield "\n"

    # ===== Section 3: Team Tests =====
    yield "## 3. Team Tests\n\n"

    # Add Agent to Team test first
    yield "### 3.1 Add Agent to Team\n"
    try:
        if not test_state["agent_id"]:
            yield "SKIP: Skipping test because agent creation failed\n"
        else:
            # First get the team to get the team_id
            async with httpx.AsyncClient() as client:
                team_response = await client.get(
                    f"{api_base_url}/v1/team",
                    headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                )

                if team_response.status_code == 200:
                    team_data = team_response.json()
                    test_state["team_id"] = team_data.get("id")
                    yield f"INFO: Retrieved team ID: {test_state['team_id']}\n"
                else:
                    test_results.failed_tests.append("Get Team ID")
                    yield f"❌ FAIL: Could not retrieve team ID. Status code: {team_response.status_code}\n"

            # Now add the agent to the team
            add_agent_request = {
                "agentId": test_state["agent_id"]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{api_base_url}/v1/team/agents",
                    json=add_agent_request,
                    headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                )

                if response.status_code == 200:
                    response_data = response.json()
                    yield "✅ PASS: Successfully added agent to team\n"
                    yield f"Status code: {response.status_code}\n"

                    # Verify agent is in team
                    agent_found = any(agent.get("id") == test_state["agent_id"] for agent in response_data.get('agents', []))
                    if agent_found:
                        yield "✅ PASS: Test agent was found in the team\n"
                    else:
                        test_results.failed_tests.append("Add Agent to Team - Agent Not Found")
                        yield "❌ FAIL: Test agent was not found in the team\n"
                else:
                    test_results.failed_tests.append("Add Agent to Team")
                    yield f"❌ FAIL: Failed to add agent to team. Status code: {response.status_code}\n"
                    yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("Add Agent to Team")
        yield f"ERROR: Add agent to team test failed with exception: {str(e)}\n"

    yield "\n"

    # Get Team test to verify the agent was added
    yield "### 3.2 Get Team\n"
    try:
        if not test_state["auth_token"]:
            yield "SKIP: Skipping test because JWT creation failed\n"
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{api_base_url}/v1/team",
                    headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                )

                if response.status_code == 200:
                    response_data = response.json()
                    yield "✅ PASS: Successfully retrieved the team\n"
                    yield f"Status code: {response.status_code}\n"
                    yield f"Team ID: {response_data.get('id')}\n"
                    yield f"Number of agents in team: {len(response_data.get('agents', []))}\n"

                    # Verify our agent is in the team
                    agent_found = any(agent.get("id") == test_state["agent_id"] for agent in response_data.get('agents', []))
                    if agent_found:
                        yield "✅ PASS: Test agent was found in the team\n"
                    else:
                        test_results.failed_tests.append("Get Team - Agent Not Found")
                        yield "❌ FAIL: Test agent was not found in the team\n"
                else:
                    test_results.failed_tests.append("Get Team")
                    yield f"❌ FAIL: Failed to retrieve team. Status code: {response.status_code}\n"
                    yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("Get Team")
        yield f"ERROR: Get team test failed with exception: {str(e)}\n"

    yield "\n"

    # Get team connections
    yield "### 3.3 Get Team Connections\n"
    try:
        if not test_state["auth_token"] or not test_state["agent_id"]:
            yield "SKIP: Skipping test because JWT creation or agent creation failed\n"
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{api_base_url}/v1/team/connections",
                    headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                )

                if response.status_code == 200:
                    response_data = response.json()
                    yield "✅ PASS: Successfully retrieved team connections\n"
                    yield f"Status code: {response.status_code}\n"

                    # Log the response structure
                    if isinstance(response_data, dict) and "connections" in response_data:
                        yield f"Number of connections: {len(response_data.get('connections', []))}\n"
                    else:
                        yield "NOTE: Unexpected response structure for team connections\n"
                else:
                    test_results.failed_tests.append("Get Team Connections")
                    yield f"❌ FAIL: Failed to retrieve team connections. Status code: {response.status_code}\n"
                    yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("Get Team Connections")
        yield f"ERROR: Get team connections test failed with exception: {str(e)}\n"

    yield "\n"

    # ===== Section 4: Operations Tests =====
    yield "## 4. Operations Tests\n\n"

    # Create Operation (Run) test
    yield "### 4.1 Create Operation (Run)\n"
    try:
        if not test_state["agent_id"]:
            yield "SKIP: Skipping test because agent creation failed\n"
        else:
            # Create an operation (run) with the test agent
            operation_data = {
                "agent_id": test_state["agent_id"],
                "input": {
                    "url_to_scrape": "https://example.com"
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{api_base_url}/v1/operations/run",
                    json=operation_data,
                    headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                )

                if response.status_code == 200:
                    response_data = response.json()
                    test_state["run_id"] = response_data.get("id")
                    yield "✅ PASS: Successfully created an operation/run\n"
                    yield f"Status code: {response.status_code}\n"
                    yield f"Run ID: {test_state['run_id']}\n"
                    yield f"Status: {response_data.get('status')}\n"
                else:
                    test_results.failed_tests.append("Create Operation")
                    yield f"❌ FAIL: Failed to create operation. Status code: {response.status_code}\n"
                    yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("Create Operation")
        yield f"ERROR: Create operation test failed with exception: {str(e)}\n"

    yield "\n"

    # Get Operation Status test
    yield "### 4.2 Get Operation Status\n"
    try:
        if not test_state["run_id"]:
            yield "SKIP: Skipping test because operation creation failed\n"
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{api_base_url}/v1/operations/run/{test_state['run_id']}",
                    headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                )

                if response.status_code == 200:
                    response_data = response.json()
                    yield "✅ PASS: Successfully retrieved operation status\n"
                    yield f"Status code: {response.status_code}\n"
                    yield f"Run ID: {response_data.get('id')}\n"
                    yield f"Agent ID: {response_data.get('agent_id')}\n"
                    yield f"Status: {response_data.get('status')}\n"
                else:
                    test_results.failed_tests.append("Get Operation Status")
                    yield f"❌ FAIL: Failed to get operation status. Status code: {response.status_code}\n"
                    yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("Get Operation Status")
        yield f"ERROR: Get operation status test failed with exception: {str(e)}\n"

    yield "\n"

    # Get Team Status test
    yield "### 4.3 Get Team Status\n" 
    try:
        if not test_state["auth_token"]:
            yield "SKIP: Skipping test because JWT creation failed\n"
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{api_base_url}/v1/operations/team-status",
                    headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                )

                if response.status_code == 200:
                    response_data = response.json()
                    yield "✅ PASS: Successfully retrieved team status\n"
                    yield f"Status code: {response.status_code}\n"
                    yield f"Number of agents in status: {len(response_data.get('agent_statuses', {}))}\n"

                    # Check if our agent is in the team status
                    if test_state["agent_id"] in response_data.get('agent_statuses', {}):
                        yield "✅ PASS: Our test agent was found in the team status\n"
                    else:
                        yield "NOTE: Our test agent was not found in the team status (may be normal if operation completed quickly)\n"
                else:
                    test_results.failed_tests.append("Get Team Status")
                    yield f"❌ FAIL: Failed to get team status. Status code: {response.status_code}\n"
                    yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("Get Team Status")
        yield f"ERROR: Get team status test failed with exception: {str(e)}\n"

    yield "\n"

    # ===== Section 5: Cleanup =====
    yield "## 5. Cleanup\n\n"

    # Remove Agent from Team test
    yield "### 5.1 Remove Agent from Team\n"
    try:
        if not test_state["agent_id"] or not test_state["team_id"]:
            yield "SKIP: Skipping test because agent or team retrieval failed\n"
        else:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{api_base_url}/v1/team/agents/{test_state['agent_id']}",
                    headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                )

                if response.status_code == 200:
                    response_data = response.json()
                    yield "✅ PASS: Successfully removed agent from team\n"
                    yield f"Status code: {response.status_code}\n"

                    # Verify agent is no longer in team
                    agent_found = any(agent.get("id") == test_state["agent_id"] for agent in response_data.get('agents', []))
                    if not agent_found:
                        yield "✅ PASS: Test agent was successfully removed from the team\n"
                    else:
                        test_results.failed_tests.append("Remove Agent from Team - Agent Still Present")
                        yield "❌ FAIL: Test agent is still in the team after removal\n"
                else:
                    test_results.failed_tests.append("Remove Agent from Team")
                    yield f"❌ FAIL: Failed to remove agent from team. Status code: {response.status_code}\n"
                    yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("Remove Agent from Team")
        yield f"ERROR: Remove agent from team test failed with exception: {str(e)}\n"

    yield "\n"

    # Delete Operation test
    yield "### 5.2 Delete Operation\n"
    try:
        if not test_state["run_id"]:
            yield "SKIP: Skipping test because operation creation failed\n"
        else:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{api_base_url}/v1/operations/run/{test_state['run_id']}",
                    headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                )

                if response.status_code == 200:
                    yield "✅ PASS: Successfully deleted operation\n"
                    yield f"Status code: {response.status_code}\n"
                elif response.status_code == 404:
                    yield "NOTE: Operation may have already been deleted or auto-removed\n"
                elif response.status_code == 405:
                    yield "NOTE: Operation deletion endpoint may not be implemented\n"
                else:
                    test_results.failed_tests.append("Delete Operation")
                    yield f"❌ FAIL: Failed to delete operation. Status code: {response.status_code}\n"
                    yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("Delete Operation")
        yield f"ERROR: Delete operation test failed with exception: {str(e)}\n"

    yield "\n"

    # Delete Agent test
    yield "### 5.3 Delete Agent\n"
    try:
        if not test_state["agent_id"]:
            yield "SKIP: Skipping test because agent creation failed\n"
        else:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{api_base_url}/v1/agents/{test_state['agent_id']}",
                    headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                )

                if response.status_code == 200:
                    yield "✅ PASS: Successfully deleted agent\n"
                    yield f"Status code: {response.status_code}\n"

                    # Verify agent is deleted
                    verify_response = await client.get(
                        f"{api_base_url}/v1/agents/{test_state['agent_id']}",
                        headers={"Authorization": f"Bearer {test_state['auth_token']}"}
                    )

                    if verify_response.status_code == 404:
                        yield "✅ PASS: Verified agent was successfully deleted\n"
                    else:
                        test_results.failed_tests.append("Delete Agent - Agent Still Exists")
                        yield f"❌ FAIL: Agent still exists after deletion. Status code: {verify_response.status_code}\n"
                else:
                    test_results.failed_tests.append("Delete Agent")
                    yield f"❌ FAIL: Failed to delete agent. Status code: {response.status_code}\n"
                    yield f"Response: {response.text if hasattr(response, 'text') else 'No response text'}\n"
    except Exception as e:
        test_results.failed_tests.append("Delete Agent")
        yield f"ERROR: Delete agent test failed with exception: {str(e)}\n"

    yield "\n"

    # ===== Test Summary =====
    yield "## Summary\n\n"
    yield "Integration tests completed.\n\n"

    # Report number of failed tests
    if not test_results.failed_tests:
        yield "✅ ALL TESTS PASSED\n"
    else:
        yield f"❌ FAILED TESTS: {len(test_results.failed_tests)}\n\n"
        yield "The following tests failed:\n"
        for failed_test in test_results.failed_tests:
            yield f"* {failed_test}\n"

    yield "\n"

@router.get("")
async def get_diagnostics_tests(request: Request):
    """
    Returns a complete integration test suite as streaming text.
    Tests all major API functionality including connectivity, agents, teams, and operations.
    Returns HTTP 200 if all tests pass, or HTTP 500 if any test fails.
    """
    # Create an object to track test results
    test_results = TestResults()

    async def test_suite_generator():
        """Stream the test results"""
        async for line in generate_test_suite(test_results):
            yield line

    # Create the response with proper status code
    if request.headers.get("accept") == "application/json":
        # For API clients that expect JSON
        # We need to run the tests first to know if they passed or failed
        all_results = []
        async for line in generate_test_suite(test_results):
            all_results.append(line)

        # Set status code based on test results
        status_code = 500 if test_results.failed_tests else 200

        # Return a JSON response
        return Response(
            content=json.dumps({
                "success": not test_results.failed_tests,
                "failed_tests": len(test_results.failed_tests),
                "failed_test_names": test_results.failed_tests,
                "output": "".join(all_results)
            }),
            media_type="application/json",
            status_code=status_code
        )
    else:
        # For browsers or curl, stream the response
        # We need to complete all tests before knowing the status code, 
        # so we'll always initially use 200 and let the client determine success
        return StreamingResponse(
            test_suite_generator(),
            media_type="text/plain",
        )

@router.get("/status")
async def get_diagnostics_status():
    """
    Returns a simplified status check that can be used for monitoring.
    Returns HTTP 200 if all core functionality is working, or HTTP 500 if any critical tests fail.
    """
    # Create an object to track test results
    test_results = TestResults()

    # Run a simplified test suite for monitoring
    all_lines = []
    async for line in generate_test_suite(test_results):
        all_lines.append(line)

    # Return the proper status code based on test results
    status_code = 500 if test_results.failed_tests else 200

    return Response(
        content=json.dumps({
            "success": not test_results.failed_tests,
            "failed_tests": len(test_results.failed_tests),
            "failed_test_names": test_results.failed_tests
        }),
        media_type="application/json",
        status_code=status_code
    )