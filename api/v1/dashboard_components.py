# api/v1/dashboard_components.py
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from models.dashboard_component import DashboardComponent
from pydantic import UUID4
import logging
from services.dashboard_components import DashboardComponentService

logger = logging.getLogger(__name__) 

router = APIRouter(prefix="/dashboard/components", tags=["dashboard_components"])

@router.post("", response_model=DashboardComponent, summary="Create a new dashboard component", 
             description="Create a new dashboard component with the provided configuration data", 
             status_code=201, 
             responses={
                 201: {"description": "Dashboard component created successfully"},
                 422: {"description": "Validation error in request data"},
                 500: {"description": "Server error during dashboard component creation"}
             })
async def create_dashboard_component(component_data: dict):
    service = DashboardComponentService()
    return await service.create_dashboard_component(component_data)

@router.get("/{component_id}", response_model=DashboardComponent, 
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
        service = DashboardComponentService()
        return await service.get_dashboard_component(component_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=List[DashboardComponent], 
            summary="List all dashboard components", 
            description="Retrieve a paginated list of all available dashboard components", 
            responses={
                200: {"description": "List of dashboard components retrieved successfully"},
                500: {"description": "Server error"}
            })
async def list_dashboard_components(limit: Optional[int] = 100, offset: Optional[int] = 0):
    service = DashboardComponentService()
    return await service.list_dashboard_components(limit, offset)

@router.put("/{component_id}", response_model=DashboardComponent, 
            summary="Update a dashboard component", 
            description="Update an existing dashboard component with new configuration data", 
            responses={
                200: {"description": "Dashboard component updated successfully"},
                404: {"description": "Dashboard component not found"},
                422: {"description": "Validation error in request data"},
                500: {"description": "Server error"}
            })
async def update_dashboard_component(component_id: UUID4, component_data: dict):
    service = DashboardComponentService()
    return await service.update_dashboard_component(component_id, component_data)

@router.delete("/{component_id}", 
               summary="Delete a dashboard component", 
               description="Permanently remove a dashboard component from the system", 
               responses={
                   200: {"description": "Dashboard component deleted successfully"},
                   404: {"description": "Dashboard component not found"},
                   500: {"description": "Server error"}
               })
async def delete_dashboard_component(component_id: UUID4):
    service = DashboardComponentService()
    return await service.delete_dashboard_component(component_id)