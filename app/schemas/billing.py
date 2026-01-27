from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from app.models.enums import BillStatus

class BillResponse(BaseModel):
    id: UUID
    amount: Decimal
    status: BillStatus
    due_date: date
    created_at: datetime
    
    class Config:
        from_attributes = True
