# api/v1/dashboards.py
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from models.dashboard import Dashboard, DashboardComponent
from pydantic import ValidationError, UUID4
import logging
from services.dashboards import DashboardService
from datetime import datetime
import traceback
from uuid import UUID as PythonUUID  # Rename to avoid confusion
logger = logging.getLogger(__name__) 

router = APIRouter(prefix="/dashboards", tags=["dashboards"])

#
# Dashboard Endpoints
#
@router.post("", response_model=Dashboard, summary="Create a new dashboard", 
             description="Create a new dashboard with the provided configuration data", 
             status_code=201, 
             responses={
                 201: {"description": "Dashboard created successfully"}, 
                 422: {"description": "Validation error in request data"}, 
                 500: {"description": "Server error during dashboard creation"}
             })
async def create_dashboard(dashboard_data: dict):
    service = DashboardService()
    return await service.create_dashboard(dashboard_data)

@router.get("/{dashboard_id}", response_model=Dashboard, 
            summary="Get dashboard by ID", 
            description="Retrieve detailed information about a specific dashboard", 
            responses={
                200: {"description": "Dashboard details retrieved successfully"}, 
                404: {"description": "Dashboard not found"}, 
                400: {"description": "Invalid UUID format"}, 
                500: {"description": "Server error"}
            })
async def get_dashboard(dashboard_id: str):
    try:
        service = DashboardService()
        return await service.get_dashboard(dashboard_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=List[Dashboard], 
            summary="List all dashboards", 
            description="Retrieve a paginated list of all available dashboards", 
            responses={
                200: {"description": "List of dashboards retrieved successfully"}, 
                500: {"description": "Server error"}
            })
async def list_dashboards(
    limit: Optional[int] = Query(100, description="Maximum number of items to return"),
    offset: Optional[int] = Query(0, description="Number of items to skip"), 
    user_id: Optional[str] = Query(None, description="Filter dashboards by user ID")
):
    service = DashboardService()
    return await service.list_dashboards(limit, offset, user_id)

@router.put("/{dashboard_id}", response_model=Dashboard, 
            summary="Update a dashboard", 
            description="Update an existing dashboard with new configuration data", 
            responses={
                200: {"description": "Dashboard updated successfully"}, 
                404: {"description": "Dashboard not found"}, 
                422: {"description": "Validation error in request data"}, 
                500: {"description": "Server error"}
            })
async def update_dashboard(dashboard_id: UUID4, dashboard_data: dict):
    service = DashboardService()
    return await service.update_dashboard(dashboard_id, dashboard_data)

@router.delete("/{dashboard_id}", 
               summary="Delete a dashboard", 
               description="Permanently remove a dashboard from the system", 
               responses={
                   200: {"description": "Dashboard deleted successfully"}, 
                   404: {"description": "Dashboard not found"}, 
                   500: {"description": "Server error"}
               })
async def delete_dashboard(dashboard_id: UUID4):
    service = DashboardService()
    return await service.delete_dashboard(dashboard_id)

#
# Dashboard Component Endpoints
#

# IMPORTANT: This route needs to come BEFORE the /components/{component_id} route
# Otherwise, FastAPI will interpret "components" as a component_id
@router.get("/components", 
            # Temporarily disable response_model for debugging
            # response_model=List[DashboardComponent], 
            summary="List all dashboard components", 
            description="Retrieve a paginated list of all available dashboard components", 
            responses={
                200: {"description": "List of dashboard components retrieved successfully"}, 
                500: {"description": "Server error"}
            })
async def list_dashboard_components(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Safe version that returns raw dictionaries instead of model objects
    """
    try:
        logging.info(f"Listing dashboard components, limit={limit}, offset={offset}")

        # Get raw data
        result = self.supabase.table("dashboard_components")\
            .select("*")\
            .range(offset, offset + limit - 1)\
            .execute()

        logging.info(f"Retrieved {len(result.data)} components")

        # Process data to ensure it's serializable and types are correct
        components = []
        for item in result.data:
            try:
                # Create a safe copy
                component_dict = dict(item)

                # Handle known fields that might need conversion
                if 'layout_cols' in component_dict and isinstance(component_dict['layout_cols'], str):
                    component_dict['layout_cols'] = int(component_dict['layout_cols'])
                if 'layout_rows' in component_dict and isinstance(component_dict['layout_rows'], str):
                    component_dict['layout_rows'] = int(component_dict['layout_rows'])

                # Handle datetime
                if 'created_at' in component_dict:
                    created_at = component_dict['created_at']
                    if hasattr(created_at, 'isoformat'):
                        component_dict['created_at'] = created_at.isoformat()
                    else:
                        component_dict['created_at'] = str(created_at)

                components.append(component_dict)
            except Exception as e:
                logging.error(f"Error processing component: {str(e)}", exc_info=True)
                # Skip this component but continue with others

        return components
    except Exception as e:
        logging.error(f"Error listing dashboard components: {str(e)}", exc_info=True)
        # Return empty list rather than raising exception
        return []
        
@router.post("/components", response_model=DashboardComponent, 
             summary="Create a new dashboard component", 
             description="Create a new dashboard component with the provided configuration", 
             status_code=201, 
             responses={
                 201: {"description": "Dashboard component created successfully"}, 
                 422: {"description": "Validation error in request data"}, 
                 500: {"description": "Server error during component creation"}
             })
async def create_dashboard_component(component_data: dict):
    service = DashboardService()
    return await service.create_dashboard_component(component_data)

@router.get("/components/{component_id}", response_model=DashboardComponent, 
            summary="Get dashboard component by ID", 
            description="Retrieve detailed information about a specific dashboard component", 
            responses={
                200: {"description": "Dashboard component details retrieved successfully"}, 
                404: {"description": "Dashboard component not found"}, 
                400: {"description": "Invalid UUID format"}, 
                500: {"description": "Server error"}
            })
async def get_dashboard_component(component_id: str):
    try:
        service = DashboardService()
        return await service.get_dashboard_component(component_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/components/{component_id}", response_model=DashboardComponent, 
            summary="Update a dashboard component", 
            description="Update an existing dashboard component with new configuration", 
            responses={
                200: {"description": "Dashboard component updated successfully"}, 
                404: {"description": "Dashboard component not found"}, 
                422: {"description": "Validation error in request data"}, 
                500: {"description": "Server error"}
            })
async def update_dashboard_component(component_id: UUID4, component_data: dict):
    service = DashboardService()
    return await service.update_dashboard_component(component_id, component_data)

@router.delete("/components/{component_id}", 
               summary="Delete a dashboard component", 
               description="Permanently remove a dashboard component from the system", 
               responses={
                   200: {"description": "Dashboard component deleted successfully"}, 
                   404: {"description": "Dashboard component not found"}, 
                   500: {"description": "Server error"}
               })
async def delete_dashboard_component(component_id: UUID4):
    service = DashboardService()
    return await service.delete_dashboard_component(component_id)