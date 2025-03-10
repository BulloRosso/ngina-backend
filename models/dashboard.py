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

class DashboardComponentBase(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    layout_cols: Optional[int] = 2
    layout_rows: Optional[int] = 2
    react_component_name: Optional[str] = None

    # Add this to make Pydantic more forgiving with type conversion
    model_config = ConfigDict(
        from_attributes=True,
        extra='ignore',  # Ignore extra fields
        str_strip_whitespace=True,  # Strip whitespace from strings
        validate_assignment=True,  # Validate on attribute assignment
        validate_default=True,  # Validate default values
        # Make UUID validation use strict=False
        json_schema_extra={
            'uuid_format': 'non-strict'
        }
    )

class DashboardComponentCreate(DashboardComponentBase):
    pass

class DashboardComponent(DashboardComponentBase):
    model_config = ConfigDict(
        from_attributes=True,
        extra='ignore',  # Ignore extra fields
        str_strip_whitespace=True,  # Strip whitespace from strings
        validate_assignment=True,  # Validate on attribute assignment
        validate_default=True,  # Validate default values
        # Make UUID validation use strict=False
        json_schema_extra={
            'uuid_format': 'non-strict'
        }
    )

    id: UUID4
    created_at: datetime




