# models/dashboard.py
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, UUID4, ConfigDict

class I18nContent(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

class Description(BaseModel):
    en: Optional[I18nContent] = None

class Layout(BaseModel):
    logoUrl: Optional[str] = None
    templateName: Optional[str] = "default"

class Style(BaseModel):
    layout: Optional[Layout] = None
    components: Optional[List[Any]] = []

class DashboardBase(BaseModel):
    configuration: Optional[Any] = None
    agents: Optional[Any] = None
    is_anonymous: Optional[bool] = True
    user_id: Optional[UUID4] = None
    description: Optional[Description] = None
    style: Optional[Style] = None

class DashboardCreate(DashboardBase):
    pass


class Dashboard(DashboardBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    created_at: datetime





