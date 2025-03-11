# models/dashboard_component.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, UUID4, ConfigDict

class DashboardComponentBase(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    layout_cols: Optional[int] = 2
    layout_rows: Optional[int] = 2
    react_component_name: Optional[str] = None

class DashboardComponentCreate(DashboardComponentBase):
    pass

class DashboardComponent(DashboardComponentBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    created_at: datetime