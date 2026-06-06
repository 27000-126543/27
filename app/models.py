from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, Boolean, Text,
    ForeignKey, Index, UniqueConstraint, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    SALES = "sales"
    SALES_MANAGER = "sales_manager"
    REGION_DIRECTOR = "region_director"
    FINANCE = "finance"
    CHANNEL_PARTNER = "channel_partner"
    AUDITOR = "auditor"


class CustomerLevel(str, enum.Enum):
    DIAMOND = "diamond"
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    NORMAL = "normal"


class ProductCategory(str, enum.Enum):
    HARDWARE = "hardware"
    SOFTWARE = "software"
    SERVICE = "service"
    CONSULTING = "consulting"
    CLOUD = "cloud"
    OTHER = "other"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class AppealStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class RebateStatus(str, enum.Enum):
    PENDING = "pending"
    CALCULATED = "calculated"
    APPROVED = "approved"
    FROZEN = "frozen"
    PAID = "paid"
    WARNING = "warning"


class LogAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    CALCULATE = "calculate"
    APPROVE = "approve"
    REJECT = "reject"
    SUBMIT = "submit"
    SYNC = "sync"
    EXPORT = "export"
    FREEZE = "freeze"
    UNFREEZE = "unfreeze"
    CORRECT = "correct"
    RECALCULATE = "recalculate"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.SALES)
    is_active = Column(Boolean, default=True)
    department = Column(String(100))
    region = Column(String(100))
    manager_id = Column(Integer, ForeignKey("users.id"))
    employee_id = Column(String(50), unique=True, index=True)
    phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manager = relationship("User", remote_side=[id], backref="subordinates")


class Salesperson(Base):
    __tablename__ = "salespersons"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    salesperson_code = Column(String(50), unique=True, nullable=False, index=True)
    tier = Column(String(20), default="T1")
    base_commission_rate = Column(Float, default=0.02)
    quota = Column(Float, default=0.0)
    region = Column(String(100))
    join_date = Column(Date, default=date.today)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="salesperson_profile")


class ChannelPartner(Base):
    __tablename__ = "channel_partners"

    id = Column(Integer, primary_key=True, index=True)
    partner_code = Column(String(50), unique=True, nullable=False, index=True)
    partner_name = Column(String(200), nullable=False)
    contact_person = Column(String(100))
    contact_email = Column(String(100))
    contact_phone = Column(String(20))
    tier = Column(String(20), default="Gold")
    base_rebate_rate = Column(Float, default=0.03)
    quarterly_budget = Column(Float, default=0.0)
    annual_budget = Column(Float, default=0.0)
    contract_start_date = Column(Date)
    contract_end_date = Column(Date)
    contract_ratio = Column(Float, default=1.0)
    region = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    customer_code = Column(String(50), unique=True, nullable=False, index=True)
    customer_name = Column(String(200), nullable=False)
    level = Column(SAEnum(CustomerLevel), default=CustomerLevel.NORMAL)
    industry = Column(String(100))
    region = Column(String(100))
    contact_person = Column(String(100))
    contact_email = Column(String(100))
    contact_phone = Column(String(20))
    channel_partner_id = Column(Integer, ForeignKey("channel_partners.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    channel_partner = relationship("ChannelPartner", backref="customers")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    product_code = Column(String(50), unique=True, nullable=False, index=True)
    product_name = Column(String(200), nullable=False)
    category = Column(SAEnum(ProductCategory), default=ProductCategory.OTHER)
    unit_price = Column(Float, default=0.0)
    cost = Column(Float, default=0.0)
    commission_rate_override = Column(Float)
    rebate_rate_override = Column(Float)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    order_date = Column(Date, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    salesperson_id = Column(Integer, ForeignKey("salespersons.id"), nullable=False)
    channel_partner_id = Column(Integer, ForeignKey("channel_partners.id"))
    total_amount = Column(Float, nullable=False, default=0.0)
    discount_amount = Column(Float, default=0.0)
    net_amount = Column(Float, nullable=False, default=0.0)
    paid_amount = Column(Float, default=0.0)
    payment_status = Column(String(20), default="unpaid")
    contract_number = Column(String(50))
    region = Column(String(100))
    crm_id = Column(String(50), index=True)
    order_system_id = Column(String(50), index=True)
    is_active = Column(Boolean, default=True)
    synced_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", backref="orders")
    salesperson = relationship("Salesperson", backref="orders")
    channel_partner = relationship("ChannelPartner", backref="orders")
    items = relationship("OrderItem", backref="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_order_date_salesperson", "order_date", "salesperson_id"),
        Index("idx_order_date_channel", "order_date", "channel_partner_id"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Float, nullable=False, default=1.0)
    unit_price = Column(Float, nullable=False, default=0.0)
    discount_rate = Column(Float, default=0.0)
    line_amount = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product")


class CommissionTierRule(Base):
    __tablename__ = "commission_tier_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    product_category = Column(SAEnum(ProductCategory))
    customer_level = Column(SAEnum(CustomerLevel))
    min_amount = Column(Float, default=0.0)
    max_amount = Column(Float)
    base_rate = Column(Float, nullable=False)
    bonus_rate = Column(Float, default=0.0)
    quota_multiplier = Column(Float, default=1.0)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    effective_from = Column(Date, default=date(2020, 1, 1))
    effective_to = Column(Date)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BonusRule(Base):
    __tablename__ = "bonus_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    rule_type = Column(String(50), nullable=False)
    threshold_amount = Column(Float, nullable=False)
    bonus_amount = Column(Float, default=0.0)
    bonus_percentage = Column(Float, default=0.0)
    period = Column(String(20), default="monthly")
    is_active = Column(Boolean, default=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CommissionRecord(Base):
    __tablename__ = "commission_records"

    id = Column(Integer, primary_key=True, index=True)
    record_code = Column(String(50), unique=True, nullable=False, index=True)
    salesperson_id = Column(Integer, ForeignKey("salespersons.id"), nullable=False, index=True)
    period_year = Column(Integer, nullable=False, index=True)
    period_month = Column(Integer, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("sales_orders.id"))
    product_category = Column(SAEnum(ProductCategory))
    customer_level = Column(SAEnum(CustomerLevel))
    base_amount = Column(Float, nullable=False, default=0.0)
    commission_rate = Column(Float, nullable=False, default=0.0)
    base_commission = Column(Float, nullable=False, default=0.0)
    bonus_amount = Column(Float, default=0.0)
    total_commission = Column(Float, nullable=False, default=0.0)
    calculation_details = Column(Text)
    approval_status = Column(SAEnum(ApprovalStatus), default=ApprovalStatus.PENDING, index=True)
    approval_level = Column(Integer, default=1)
    current_approver_id = Column(Integer, ForeignKey("users.id"))
    is_paid = Column(Boolean, default=False)
    paid_at = Column(DateTime)
    payment_reference = Column(String(100))
    remarks = Column(Text)
    is_corrected = Column(Boolean, default=False)
    original_record_id = Column(Integer, ForeignKey("commission_records.id"))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    salesperson = relationship("Salesperson", backref="commissions")
    order = relationship("SalesOrder")
    current_approver = relationship("User", foreign_keys=[current_approver_id])

    __table_args__ = (
        Index("idx_commission_period", "period_year", "period_month"),
        Index("idx_commission_salesperson_period", "salesperson_id", "period_year", "period_month"),
    )


class RebateTierRule(Base):
    __tablename__ = "rebate_tier_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    tier = Column(String(20))
    min_amount = Column(Float, default=0.0)
    max_amount = Column(Float)
    rebate_rate = Column(Float, nullable=False)
    bonus_rate = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RebateRecord(Base):
    __tablename__ = "rebate_records"

    id = Column(Integer, primary_key=True, index=True)
    record_code = Column(String(50), unique=True, nullable=False, index=True)
    channel_partner_id = Column(Integer, ForeignKey("channel_partners.id"), nullable=False, index=True)
    period_year = Column(Integer, nullable=False, index=True)
    period_quarter = Column(Integer, nullable=False, index=True)
    total_sales = Column(Float, nullable=False, default=0.0)
    contract_ratio = Column(Float, default=1.0)
    adjusted_sales = Column(Float, nullable=False, default=0.0)
    rebate_rate = Column(Float, nullable=False, default=0.0)
    base_rebate = Column(Float, nullable=False, default=0.0)
    bonus_rebate = Column(Float, default=0.0)
    total_rebate = Column(Float, nullable=False, default=0.0)
    budget_amount = Column(Float, default=0.0)
    budget_utilization = Column(Float, default=0.0)
    status = Column(SAEnum(RebateStatus), default=RebateStatus.PENDING, index=True)
    approval_status = Column(SAEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    warning_message = Column(Text)
    is_frozen = Column(Boolean, default=False)
    frozen_reason = Column(Text)
    is_paid = Column(Boolean, default=False)
    paid_at = Column(DateTime)
    calculation_details = Column(Text)
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    channel_partner = relationship("ChannelPartner", backref="rebates")

    __table_args__ = (
        UniqueConstraint("channel_partner_id", "period_year", "period_quarter",
                         name="uq_rebate_partner_quarter"),
    )


class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    id = Column(Integer, primary_key=True, index=True)
    approval_type = Column(String(50), nullable=False)
    target_id = Column(Integer, nullable=False, index=True)
    target_code = Column(String(50), index=True)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approval_level = Column(Integer, default=1)
    action = Column(SAEnum(ApprovalStatus), nullable=False)
    comments = Column(Text)
    approval_date = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    approver = relationship("User")


class Appeal(Base):
    __tablename__ = "appeals"

    id = Column(Integer, primary_key=True, index=True)
    appeal_code = Column(String(50), unique=True, nullable=False, index=True)
    appellant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    appellant_type = Column(String(20), default="salesperson")
    commission_record_id = Column(Integer, ForeignKey("commission_records.id"))
    rebate_record_id = Column(Integer, ForeignKey("rebate_records.id"))
    appeal_type = Column(String(50), nullable=False)
    reason = Column(Text, nullable=False)
    evidence = Column(Text)
    status = Column(SAEnum(AppealStatus), default=AppealStatus.SUBMITTED, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"))
    review_comments = Column(Text)
    review_date = Column(DateTime)
    is_resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    appellant = relationship("User", foreign_keys=[appellant_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    commission_record = relationship("CommissionRecord", backref="appeals")
    rebate_record = relationship("RebateRecord", backref="appeals")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String(50), index=True)
    action = Column(SAEnum(LogAction), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer)
    entity_code = Column(String(50))
    field_name = Column(String(100))
    old_value = Column(Text)
    new_value = Column(Text)
    details = Column(Text)
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_timestamp_action", "timestamp", "action"),
    )


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    report_code = Column(String(50), unique=True, nullable=False, index=True)
    report_type = Column(String(50), nullable=False)
    period_year = Column(Integer)
    period_month = Column(Integer)
    period_quarter = Column(Integer)
    title = Column(String(200), nullable=False)
    summary = Column(Text)
    file_path_pdf = Column(String(500))
    file_path_excel = Column(String(500))
    generated_by = Column(Integer, ForeignKey("users.id"))
    generated_at = Column(DateTime, default=datetime.utcnow, index=True)
    is_auto_generated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PaymentInstruction(Base):
    __tablename__ = "payment_instructions"

    id = Column(Integer, primary_key=True, index=True)
    instruction_code = Column(String(50), unique=True, nullable=False, index=True)
    payment_type = Column(String(20), nullable=False)
    target_id = Column(Integer, nullable=False)
    target_code = Column(String(50), index=True)
    payee_name = Column(String(200), nullable=False)
    payee_account = Column(String(100))
    payee_bank = Column(String(200))
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="CNY")
    status = Column(String(20), default="pending", index=True)
    finance_reference = Column(String(100))
    pushed_to_finance_at = Column(DateTime)
    confirmed_at = Column(DateTime)
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DataSyncLog(Base):
    __tablename__ = "data_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    sync_type = Column(String(50), nullable=False)
    source_system = Column(String(50), nullable=False)
    records_processed = Column(Integer, default=0)
    records_succeeded = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)
    status = Column(String(20), default="running")
