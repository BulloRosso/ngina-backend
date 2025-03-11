# api/v1/dashboards.py
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from models.dashboard import Dashboard
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

