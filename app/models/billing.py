"""Domain 9: Billing Model"""

from sqlalchemy import Column, Date, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, SchoolScopedMixin
from app.models.enums import BillStatus


class Bill(BaseModel, SchoolScopedMixin):
    """
    Invoice/billing management for schools.
    Tracks payment status and due dates.
    """
    __tablename__ = "bills"
    
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(ENUM(BillStatus, name="bill_status"), default=BillStatus.PENDING, nullable=False, index=True)
    due_date = Column(Date, nullable=False)
    
    # Relationships
    school = relationship("School", back_populates="bills")
    
    def __repr__(self) -> str:
        return f"<Bill {self.amount} - {self.status}>"
