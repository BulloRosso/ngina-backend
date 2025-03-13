# api/v1/dashboardkpi.py
from fastapi import APIRouter, HTTPException, Depends, Path, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, Union
from uuid import UUID, uuid4
import logging
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboards/kpi", tags=["dashboards"])

class KpiResponse(BaseModel):
    """Response model for KPI data"""
    value: Union[int, float]
    label: Optional[str] = None
    trend: Optional[float] = None  # Percentage change
    trend_direction: Optional[str] = None  # "up", "down", or "stable"

# Mock KPI data for demonstration
MOCK_KPI_DATA = {
    "total_sales": {
        "value": 1234567,
        "label": "Total Sales",
        "trend": 5.2,
        "trend_direction": "up"
    },
    "active_users": {
        "value": 7856,
        "label": "Active Users",
        "trend": -2.1,
        "trend_direction": "down"
    },
    "support_tickets": {
        "value": 423,
        "label": "Open Tickets",
        "trend": 12.8,
        "trend_direction": "up"
    },
    "response_time": {
        "value": 4.2,
        "label": "Avg. Response Time (hrs)",
        "trend": -8.5,
        "trend_direction": "down"
    },
    "revenue": {
        "value": 458934,
        "label": "Monthly Revenue",
        "trend": 3.7,
        "trend_direction": "up"
    },
    "conversion_rate": {
        "value": 3.45,
        "label": "Conversion Rate (%)",
        "trend": 0.8,
        "trend_direction": "stable"
    }
}

@router.get("/{kpi_name}", response_model=KpiResponse)
async def get_kpi_data(
    kpi_name: str = Path(..., description="Name of the KPI to retrieve"),
    agent_id: Optional[str] = Query(None, description="Optional agent ID for agent-specific KPIs")
):
    """
    Retrieve KPI data by name.

    In a real implementation, this would fetch data from a database or analytics service.
    For this demo, we return mock data or generate random data for unknown KPIs.
    """
    logger.info(f"KPI request: {kpi_name} for agent: {agent_id}")

    try:
        # Check if we have mock data for this KPI
        if kpi_name in MOCK_KPI_DATA:
            # If agent_id is provided, we could modify the response based on the agent
            # For now, we'll just return the mock data with a small random variation
            kpi_data = MOCK_KPI_DATA[kpi_name].copy()

            if agent_id:
                # Add a small variance for agent-specific data
                variance = random.uniform(-0.1, 0.1)  # ±10% variance
                kpi_data["value"] = kpi_data["value"] * (1 + variance)

                # Round to appropriate precision
                if isinstance(kpi_data["value"], int):
                    kpi_data["value"] = int(kpi_data["value"])
                else:
                    kpi_data["value"] = round(kpi_data["value"], 2)

                # Update trend based on variance
                kpi_data["trend"] = kpi_data["trend"] * (1 + variance)
                kpi_data["trend"] = round(kpi_data["trend"], 1)

            return kpi_data
        else:
            # Generate random data for unknown KPIs
            random_value = random.randint(100, 10000)
            random_trend = random.uniform(-15.0, 15.0)
            trend_direction = "up" if random_trend > 0 else "down" if random_trend < 0 else "stable"

            return {
                "value": random_value,
                "label": kpi_name.replace("_", " ").title(),
                "trend": round(random_trend, 1),
                "trend_direction": trend_direction
            }

    except Exception as e:
        logger.error(f"Error retrieving KPI data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve KPI data for {kpi_name}"
        )

@router.get("/agent/{agent_id}/{kpi_name}", response_model=KpiResponse)
async def get_agent_kpi_data(
    agent_id: str = Path(..., description="ID of the agent"),
    kpi_name: str = Path(..., description="Name of the KPI to retrieve")
):
    """
    Retrieve agent-specific KPI data.

    This is a convenience endpoint that calls the main KPI endpoint with the agent_id.
    """
    return await get_kpi_data(kpi_name=kpi_name, agent_id=agent_id, user_id=user_id)