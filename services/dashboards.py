# services/dashboards.py
from fastapi import HTTPException
from typing import List, Dict, Any, Optional
from models.dashboard import Dashboard, DashboardCreate, DashboardComponent, DashboardComponentCreate
from supabase import create_client
import logging
from pydantic import ValidationError, UUID4
import os
import traceback
import sys

logger = logging.getLogger(__name__)

class DashboardService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

    #
    # Dashboard CRUD Operations
    #
    async def create_dashboard(self, dashboard_data: dict) -> Dashboard:
        try:
            # Prepare the data for Supabase
            insert_data = {
                "configuration": dashboard_data.get("configuration"),
                "agents": dashboard_data.get("agents"),
                "is_anonymous": dashboard_data.get("is_anonymous", True),
                "user_id": dashboard_data.get("user_id"),
                "description": dashboard_data.get("description"),
                "style": dashboard_data.get("style")
            }

            result = self.supabase.table("dashboards").insert(insert_data).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="Failed to create dashboard")

            return Dashboard.model_validate(result.data[0])

        except Exception as e:
            logging.error(f"Error creating dashboard: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create dashboard: {str(e)}")

    async def get_dashboard(self, dashboard_id: str) -> Dashboard:
        try:
            # Validate UUID format
            UUID4(dashboard_id)

            result = self.supabase.table("dashboards")\
                .select("*")\
                .eq("id", dashboard_id)\
                .execute()

            logging.info(f"Supabase result: {result}")

            if not result.data:
                raise HTTPException(status_code=404, detail="Dashboard not found")

            try:
                # Add debug logging for the data
                logging.info(f"Raw dashboard data: {result.data[0]}")
                return Dashboard.model_validate(result.data[0])
            except ValidationError as e:
                logging.error(f"Validation error: {str(e)}")
                raise HTTPException(
                    status_code=422,
                    detail=f"Data validation error: {str(e)}"
                )
            except Exception as e:
                logging.error(f"Error processing dashboard data: {str(e)}")
                raise

        except ValidationError as e:
            error_messages = []
            for error in e.errors():
                field_path = " -> ".join(str(x) for x in error["loc"])
                error_messages.append({
                    "field": field_path,
                    "error": error["msg"],
                    "type": error["type"]
                })
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation error",
                    "errors": error_messages
                }
            )
        except Exception as e:
            logging.error(f"Error getting dashboard: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get dashboard: {str(e)}")

    async def list_dashboards(self, limit: int = 100, offset: int = 0, user_id: Optional[str] = None) -> List[Dashboard]:
        try:
            query = self.supabase.table("dashboards").select("*")

            # Filter by user_id if provided
            if user_id:
                query = query.eq("user_id", user_id)

            result = query.range(offset, offset + limit - 1).execute()

            logging.info(f"Raw data from Supabase: {result.data}")

            dashboards = []
            for item in result.data:
                try:
                    dashboard = Dashboard.model_validate(item)
                    dashboards.append(dashboard)
                except ValidationError as e:
                    logging.error(f"Validation error for dashboard {item.get('id')}: {str(e)}")
                    # Continue processing other dashboards even if one fails
                    continue

            return dashboards

        except ValidationError as e:
            error_messages = []
            for error in e.errors():
                field_path = " -> ".join(str(x) for x in error["loc"])
                error_messages.append({
                    "field": field_path,
                    "error": error["msg"],
                    "type": error["type"]
                })
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation error",
                    "errors": error_messages
                }
            )
        except Exception as e:
            logging.error(f"Error listing dashboards: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to list dashboards: {str(e)}")

    async def update_dashboard(self, dashboard_id: UUID4, dashboard_data: dict) -> Dashboard:
        try:
            # Create a DashboardCreate model for validation
            dashboard = DashboardCreate(**dashboard_data)

            # Map the model data back to a dictionary for Supabase
            update_data = {
                "configuration": dashboard_data.get("configuration"),
                "agents": dashboard_data.get("agents"),
                "is_anonymous": dashboard.is_anonymous,
                "user_id": dashboard.user_id,
                "description": dashboard_data.get("description"),
                "style": dashboard_data.get("style")
            }

            logging.info(f"Updating dashboard with data: {update_data}")

            result = self.supabase.table("dashboards")\
                .update(update_data)\
                .eq("id", str(dashboard_id))\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Dashboard not found")

            return Dashboard.model_validate(result.data[0])

        except ValidationError as e:
            error_messages = []
            for error in e.errors():
                field_path = " -> ".join(str(x) for x in error["loc"])
                error_messages.append({
                    "field": field_path,
                    "error": error["msg"],
                    "type": error["type"]
                })
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation error",
                    "errors": error_messages
                }
            )
        except Exception as e:
            logging.error(f"Error updating dashboard: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to update dashboard: {str(e)}")

    async def delete_dashboard(self, dashboard_id: UUID4) -> bool:
        try:
            result = self.supabase.table("dashboards")\
                .delete()\
                .eq("id", str(dashboard_id))\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Dashboard not found")

            return True

        except Exception as e:
            logging.error(f"Error deleting dashboard: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete dashboard: {str(e)}")

    #
    # Dashboard Component CRUD Operations
    #
    async def create_dashboard_component(self, component_data: dict) -> DashboardComponent:
        try:
            # Prepare the data for Supabase
            insert_data = {
                "name": component_data.get("name"),
                "type": component_data.get("type"),
                "layout_cols": component_data.get("layout_cols", 2),
                "layout_rows": component_data.get("layout_rows", 2),
                "react_component_name": component_data.get("react_component_name")
            }

            result = self.supabase.table("dashboard_components").insert(insert_data).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="Failed to create dashboard component")

            return DashboardComponent.model_validate(result.data[0])

        except Exception as e:
            logging.error(f"Error creating dashboard component: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create dashboard component: {str(e)}")

    async def get_dashboard_component(self, component_id: str) -> DashboardComponent:
        try:
            logging.info(f"Fetching dashboard component with id={component_id}")

            # Validate UUID format
            try:
                UUID4(component_id)
            except ValueError as e:
                logging.error(f"Invalid UUID format for component_id={component_id}: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Invalid UUID format: {str(e)}")

            result = self.supabase.table("dashboard_components")\
                .select("*")\
                .eq("id", component_id)\
                .execute()

            if not result.data:
                logging.error(f"Dashboard component not found with id={component_id}")
                raise HTTPException(status_code=404, detail="Dashboard component not found")

            try:
                logging.info(f"Retrieved dashboard component data: {result.data[0]}")

                # Convert numeric string values to integers if needed
                item = result.data[0]
                if 'layout_cols' in item and isinstance(item['layout_cols'], str):
                    item['layout_cols'] = int(item['layout_cols'])
                if 'layout_rows' in item and isinstance(item['layout_rows'], str):
                    item['layout_rows'] = int(item['layout_rows'])

                return DashboardComponent.model_validate(item)
            except ValidationError as e:
                logging.error(f"Validation error: {str(e)}")
                raise HTTPException(
                    status_code=422,
                    detail=f"Data validation error: {str(e)}"
                )

        except ValidationError as e:
            error_messages = []
            for error in e.errors():
                field_path = " -> ".join(str(x) for x in error["loc"])
                error_messages.append({
                    "field": field_path,
                    "error": error["msg"],
                    "type": error["type"]
                })
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation error",
                    "errors": error_messages
                }
            )
        except Exception as e:
            logging.error(f"Error getting dashboard component: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get dashboard component: {str(e)}")

    async def list_dashboard_components(self, limit: int = 100, offset: int = 0) -> List[DashboardComponent]:
        try:
            logging.info(f"Fetching dashboard components with limit={limit}, offset={offset}")

            # Direct SQL query to ensure we're getting exactly what's in the database
            result = self.supabase.table("dashboard_components")\
                .select("*")\
                .range(offset, offset + limit - 1)\
                .execute()

            logging.info(f"Retrieved {len(result.data)} dashboard components from Supabase")
            if result.data:
                logging.info(f"Sample component data: {result.data[0]}")

            components = []
            for item in result.data:
                try:
                    # Convert numeric string values to integers if needed
                    if 'layout_cols' in item and isinstance(item['layout_cols'], str):
                        item['layout_cols'] = int(item['layout_cols'])
                    if 'layout_rows' in item and isinstance(item['layout_rows'], str):
                        item['layout_rows'] = int(item['layout_rows'])

                    component = DashboardComponent.model_validate(item)
                    components.append(component)
                except ValidationError as e:
                    logging.error(f"Validation error for component {item.get('id')}: {str(e)}")
                    # Log the actual item data to see what's wrong
                    logging.error(f"Item data: {item}")
                    # Continue processing other components even if one fails
                    continue
                except Exception as e:
                    logging.error(f"Unexpected error processing component {item.get('id')}: {str(e)}")
                    logging.error(f"Item data: {item}")
                    continue

            return components

        except ValidationError as e:
            error_messages = []
            for error in e.errors():
                field_path = " -> ".join(str(x) for x in error["loc"])
                error_messages.append({
                    "field": field_path,
                    "error": error["msg"],
                    "type": error["type"]
                })
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation error",
                    "errors": error_messages
                }
            )
        except Exception as e:
            logging.error(f"Error listing dashboard components: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to list dashboard components: {str(e)}")

    async def update_dashboard_component(self, component_id: UUID4, component_data: dict) -> DashboardComponent:
        try:
            # Create a DashboardComponentCreate model for validation
            component = DashboardComponentCreate(**component_data)

            # Map the model data back to a dictionary for Supabase
            update_data = {
                "name": component.name,
                "type": component.type,
                "layout_cols": component.layout_cols,
                "layout_rows": component.layout_rows,
                "react_component_name": component.react_component_name
            }

            result = self.supabase.table("dashboard_components")\
                .update(update_data)\
                .eq("id", str(component_id))\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Dashboard component not found")

            return DashboardComponent.model_validate(result.data[0])

        except ValidationError as e:
            error_messages = []
            for error in e.errors():
                field_path = " -> ".join(str(x) for x in error["loc"])
                error_messages.append({
                    "field": field_path,
                    "error": error["msg"],
                    "type": error["type"]
                })
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation error",
                    "errors": error_messages
                }
            )
        except Exception as e:
            logging.error(f"Error updating dashboard component: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to update dashboard component: {str(e)}")

    async def delete_dashboard_component(self, component_id: UUID4) -> bool:
        try:
            result = self.supabase.table("dashboard_components")\
                .delete()\
                .eq("id", str(component_id))\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Dashboard component not found")

            return True

        except Exception as e:
            logging.error(f"Error deleting dashboard component: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete dashboard component: {str(e)}")

def diagnose_uuid_error(context="Unknown"):
    """
    Function to add to the code at key points to find where UUID validation is failing
    """
    # Get the current exception info
    exc_type, exc_value, exc_traceback = sys.exc_info()

    if exc_type and "badly formed hexadecimal" in str(exc_value):
        logging.error(f"UUID ERROR DETECTED at {context}!")
        logging.error(f"Error message: {str(exc_value)}")

        # Print the stack trace
        stack_trace = traceback.format_exception(exc_type, exc_value, exc_traceback)
        logging.error("Stack trace:")
        for line in stack_trace:
            logging.error(line.strip())

        # Try to get the problematic object from the frame locals
        frame = traceback.extract_tb(exc_traceback)[-1]
        logging.error(f"Error occurred in file {frame.filename}, line {frame.lineno}, in {frame.name}")

        # Try to inspect locals
        frame_obj = sys._current_frames().get(threading.get_ident())
        if frame_obj:
            local_vars = frame_obj.f_locals
            logging.error("Local variables:")
            for key, value in local_vars.items():
                if 'id' in key.lower() or 'uuid' in key.lower():
                    logging.error(f"  {key}: {value} (type: {type(value).__name__})")