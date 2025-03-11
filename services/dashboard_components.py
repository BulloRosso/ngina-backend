# services/dashboard_components.py
from fastapi import HTTPException
from typing import List
from models.dashboard_component import DashboardComponent, DashboardComponentCreate
from supabase import create_client
import logging
from pydantic import ValidationError, UUID4
import os

logger = logging.getLogger(__name__)

class DashboardComponentService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

    async def create_dashboard_component(self, component_data: dict) -> DashboardComponent:
        try:
            # Prepare the data for Supabase directly
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
            # Validate UUID format
            UUID4(component_id)

            result = self.supabase.table("dashboard_components")\
                .select("*")\
                .eq("id", component_id)\
                .execute()

            logging.info(f"Supabase result: {result}")

            if not result.data:
                raise HTTPException(status_code=404, detail="Dashboard component not found")

            try:
                # Add debug logging for the data
                logging.info(f"Raw dashboard component data: {result.data[0]}")
                return DashboardComponent.model_validate(result.data[0])
            except ValidationError as e:
                logging.error(f"Validation error: {str(e)}")
                raise HTTPException(
                    status_code=422,
                    detail=f"Data validation error: {str(e)}"
                )
            except Exception as e:
                logging.error(f"Error processing dashboard component data: {str(e)}")
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
            logging.error(f"Error getting dashboard component: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get dashboard component: {str(e)}")

    async def list_dashboard_components(self, limit: int = 100, offset: int = 0) -> List[DashboardComponent]:
        try:
            result = self.supabase.table("dashboard_components")\
                .select("*")\
                .range(offset, offset + limit - 1)\
                .execute()

            logging.info(f"Raw data from Supabase: {result.data}")

            components = []
            for item in result.data:
                try:
                    component = DashboardComponent.model_validate(item)
                    components.append(component)
                except ValidationError as e:
                    logging.error(f"Validation error for dashboard component {item.get('id')}: {str(e)}")
                    # Continue processing other components even if one fails
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

            logging.info(f"Updating dashboard component with data: {update_data}")

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