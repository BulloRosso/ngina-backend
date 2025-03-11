# services/dashboards.py
from fastapi import HTTPException
from typing import List, Dict, Any, Optional
from models.dashboard import Dashboard, DashboardCreate
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

  