from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import Optional, List, Dict
from app.models import (
    UserRole, CustomerLevel, ProductCategory, ApprovalStatus,
    AppealStatus, RebateStatus
)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    department: Optional[str] = None
    region: Optional[str] = None
    employee_id: Optional[str] = None

    class Config:
        from_attributes = True


class SalespersonOut(BaseModel):
    id: int
    salesperson_code: str
    tier: str
    base_commission_rate: float
    quota: float
    region: Optional[str] = None
    user: Optional[UserOut] = None

    class Config:
        from_attributes = True


class ChannelPartnerOut(BaseModel):
    id: int
    partner_code: str
    partner_name: str
    tier: str
    base_rebate_rate: float
    quarterly_budget: float
    annual_budget: float
    contract_ratio: float
    region: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class CommissionRecordOut(BaseModel):
    id: int
    record_code: str
    salesperson_id: int
    period_year: int
    period_month: int
    base_amount: float
    commission_rate: float
    base_commission: float
    bonus_amount: float
    total_commission: float
    approval_status: ApprovalStatus
    approval_level: int
    is_paid: bool
    product_category: Optional[ProductCategory] = None
    customer_level: Optional[CustomerLevel] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RebateRecordOut(BaseModel):
    id: int
    record_code: str
    channel_partner_id: int
    period_year: int
    period_quarter: int
    total_sales: float
    contract_ratio: float
    adjusted_sales: float
    rebate_rate: float
    base_rebate: float
    bonus_rebate: float
    total_rebate: float
    budget_amount: float
    budget_utilization: float
    status: RebateStatus
    approval_status: ApprovalStatus
    is_frozen: bool
    warning_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CalculateCommissionRequest(BaseModel):
    year: int
    month: int
    force_recalculate: bool = False


class CalculateRebateRequest(BaseModel):
    year: int
    quarter: int
    force_recalculate: bool = False


class ApprovalRequest(BaseModel):
    comments: Optional[str] = None


class AppealSubmitRequest(BaseModel):
    appeal_type: str
    reason: str
    commission_record_id: Optional[int] = None
    rebate_record_id: Optional[int] = None
    evidence: Optional[str] = None


class AppealReviewRequest(BaseModel):
    approved: bool
    review_comments: str


class DataSyncRequest(BaseModel):
    sync_type: str = "all"
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class QueryCommissionRequest(BaseModel):
    salesperson_id: Optional[int] = None
    salesperson_code: Optional[str] = None
    period_year: Optional[int] = None
    period_month: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    approval_status: Optional[ApprovalStatus] = None
    region: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    page: int = 1
    page_size: int = 50


class QueryRebateRequest(BaseModel):
    channel_partner_id: Optional[int] = None
    partner_code: Optional[str] = None
    period_year: Optional[int] = None
    period_quarter: Optional[int] = None
    status: Optional[RebateStatus] = None
    region: Optional[str] = None
    is_frozen: Optional[bool] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    page: int = 1
    page_size: int = 50


class GenericResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Dict] = None
