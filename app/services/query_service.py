from datetime import date, datetime
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models import (
    CommissionRecord, RebateRecord, SalesOrder, ApprovalRecord,
    AuditLog, Salesperson, ChannelPartner, Customer, PaymentInstruction,
    ApprovalStatus, RebateStatus, User
)


class QueryService:
    """查询与批量导出 - 多条件组合查询、审批记录查询"""

    def __init__(self, db: Session):
        self.db = db

    def query_commissions(self,
                          salesperson_id: int = None,
                          salesperson_code: str = None,
                          period_year: int = None,
                          period_month: int = None,
                          start_date: date = None,
                          end_date: date = None,
                          approval_status: ApprovalStatus = None,
                          region: str = None,
                          product_category: str = None,
                          customer_level: str = None,
                          min_amount: float = None,
                          max_amount: float = None,
                          page: int = 1,
                          page_size: int = 50) -> Tuple[List[Dict], int]:
        """组合查询佣金明细"""
        query = self.db.query(CommissionRecord)

        if salesperson_id:
            query = query.filter(CommissionRecord.salesperson_id == salesperson_id)
        if salesperson_code:
            query = query.join(Salesperson).filter(Salesperson.salesperson_code == salesperson_code)
        if period_year:
            query = query.filter(CommissionRecord.period_year == period_year)
        if period_month:
            query = query.filter(CommissionRecord.period_month == period_month)
        if approval_status:
            query = query.filter(CommissionRecord.approval_status == approval_status)
        if region:
            query = query.join(Salesperson).filter(Salesperson.region == region)
        if product_category:
            query = query.filter(CommissionRecord.product_category == product_category)
        if customer_level:
            query = query.filter(CommissionRecord.customer_level == customer_level)
        if min_amount is not None:
            query = query.filter(CommissionRecord.total_commission >= min_amount)
        if max_amount is not None:
            query = query.filter(CommissionRecord.total_commission <= max_amount)
        if start_date or end_date:
            query = query.join(SalesOrder)
            if start_date:
                query = query.filter(SalesOrder.order_date >= start_date)
            if end_date:
                query = query.filter(SalesOrder.order_date <= end_date)

        total = query.count()

        records = query.order_by(CommissionRecord.created_at.desc()) \
            .offset((page - 1) * page_size) \
            .limit(page_size) \
            .all()

        result = []
        for r in records:
            result.append({
                "id": r.id, "code": r.record_code,
                "salesperson_id": r.salesperson_id,
                "order_id": r.order_id,
                "original_record_id": r.original_record_id,
                "salesperson_name": r.salesperson.user.full_name if r.salesperson and r.salesperson.user else None,
                "salesperson_code": r.salesperson.salesperson_code if r.salesperson else None,
                "period": f"{r.period_year}-{r.period_month:02d}",
                "order_number": r.order.order_number if r.order else None,
                "product_category": r.product_category.value if r.product_category else None,
                "customer_level": r.customer_level.value if r.customer_level else None,
                "base_amount": r.base_amount,
                "commission_rate": r.commission_rate,
                "base_commission": r.base_commission,
                "bonus_amount": r.bonus_amount,
                "total_commission": r.total_commission,
                "approval_status": r.approval_status.value,
                "is_paid": r.is_paid,
                "is_corrected": r.is_corrected,
                "remarks": r.remarks,
                "created_at": r.created_at.isoformat() if r.created_at else None
            })

        return result, total

    def query_rebates(self,
                      channel_partner_id: int = None,
                      partner_code: str = None,
                      period_year: int = None,
                      period_quarter: int = None,
                      status: RebateStatus = None,
                      region: str = None,
                      is_frozen: bool = None,
                      min_amount: float = None,
                      max_amount: float = None,
                      page: int = 1,
                      page_size: int = 50) -> Tuple[List[Dict], int]:
        """组合查询渠道返利明细"""
        query = self.db.query(RebateRecord)

        if channel_partner_id:
            query = query.filter(RebateRecord.channel_partner_id == channel_partner_id)
        if partner_code:
            query = query.join(ChannelPartner).filter(ChannelPartner.partner_code == partner_code)
        if period_year:
            query = query.filter(RebateRecord.period_year == period_year)
        if period_quarter:
            query = query.filter(RebateRecord.period_quarter == period_quarter)
        if status:
            query = query.filter(RebateRecord.status == status)
        if region:
            query = query.join(ChannelPartner).filter(ChannelPartner.region == region)
        if is_frozen is not None:
            query = query.filter(RebateRecord.is_frozen == is_frozen)
        if min_amount is not None:
            query = query.filter(RebateRecord.total_rebate >= min_amount)
        if max_amount is not None:
            query = query.filter(RebateRecord.total_rebate <= max_amount)

        total = query.count()
        records = query.order_by(RebateRecord.created_at.desc()) \
            .offset((page - 1) * page_size) \
            .limit(page_size) \
            .all()

        result = []
        for r in records:
            result.append({
                "id": r.id, "code": r.record_code,
                "partner_id": r.channel_partner_id,
                "partner_name": r.channel_partner.partner_name if r.channel_partner else None,
                "partner_code": r.channel_partner.partner_code if r.channel_partner else None,
                "period": f"{r.period_year} Q{r.period_quarter}",
                "total_sales": r.total_sales,
                "contract_ratio": r.contract_ratio,
                "adjusted_sales": r.adjusted_sales,
                "rebate_rate": r.rebate_rate,
                "base_rebate": r.base_rebate,
                "bonus_rebate": r.bonus_rebate,
                "total_rebate": r.total_rebate,
                "budget_amount": r.budget_amount,
                "budget_utilization": r.budget_utilization,
                "status": r.status.value,
                "is_frozen": r.is_frozen,
                "warning_message": r.warning_message,
                "created_at": r.created_at.isoformat() if r.created_at else None
            })

        return result, total

    def query_approval_history(self,
                                target_type: str = None,
                                target_id: int = None,
                                approver_id: int = None,
                                start_date: date = None,
                                end_date: date = None,
                                action: ApprovalStatus = None,
                                page: int = 1,
                                page_size: int = 50) -> Tuple[List[Dict], int]:
        """查询审批记录"""
        query = self.db.query(ApprovalRecord)

        if target_type:
            query = query.filter(ApprovalRecord.approval_type == target_type)
        if target_id:
            query = query.filter(ApprovalRecord.target_id == target_id)
        if approver_id:
            query = query.filter(ApprovalRecord.approver_id == approver_id)
        if action:
            query = query.filter(ApprovalRecord.action == action)
        if start_date:
            query = query.filter(ApprovalRecord.approval_date >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(ApprovalRecord.approval_date <= datetime.combine(end_date, datetime.max.time()))

        total = query.count()
        records = query.order_by(ApprovalRecord.approval_date.desc()) \
            .offset((page - 1) * page_size) \
            .limit(page_size) \
            .all()

        result = []
        for r in records:
            result.append({
                "id": r.id,
                "type": r.approval_type,
                "target_id": r.target_id,
                "target_code": r.target_code,
                "approver": r.approver.full_name if r.approver else None,
                "level": r.approval_level,
                "action": r.action.value,
                "comments": r.comments,
                "approval_date": r.approval_date.isoformat() if r.approval_date else None
            })

        return result, total

    def query_orders(self,
                     salesperson_id: int = None,
                     channel_partner_id: int = None,
                     customer_id: int = None,
                     start_date: date = None,
                     end_date: date = None,
                     payment_status: str = None,
                     region: str = None,
                     page: int = 1,
                     page_size: int = 50) -> Tuple[List[Dict], int]:
        """查询订单明细"""
        query = self.db.query(SalesOrder)

        if salesperson_id:
            query = query.filter(SalesOrder.salesperson_id == salesperson_id)
        if channel_partner_id:
            query = query.filter(SalesOrder.channel_partner_id == channel_partner_id)
        if customer_id:
            query = query.filter(SalesOrder.customer_id == customer_id)
        if start_date:
            query = query.filter(SalesOrder.order_date >= start_date)
        if end_date:
            query = query.filter(SalesOrder.order_date <= end_date)
        if payment_status:
            query = query.filter(SalesOrder.payment_status == payment_status)
        if region:
            query = query.filter(SalesOrder.region == region)

        total = query.count()
        records = query.order_by(SalesOrder.order_date.desc()) \
            .offset((page - 1) * page_size) \
            .limit(page_size) \
            .all()

        result = []
        for o in records:
            result.append({
                "id": o.id,
                "order_number": o.order_number,
                "order_date": o.order_date.isoformat() if o.order_date else None,
                "customer": o.customer.customer_name if o.customer else None,
                "salesperson": o.salesperson.user.full_name if o.salesperson and o.salesperson.user else None,
                "channel_partner": o.channel_partner.partner_name if o.channel_partner else None,
                "total_amount": o.total_amount,
                "net_amount": o.net_amount,
                "paid_amount": o.paid_amount,
                "payment_status": o.payment_status,
                "region": o.region,
                "contract_number": o.contract_number
            })

        return result, total

    def get_dashboard_data(self) -> Dict:
        """获取仪表盘概览数据"""
        from datetime import datetime
        now = datetime.now()
        year = now.year
        month = now.month

        comms_current = self.db.query(CommissionRecord).filter(
            CommissionRecord.period_year == year,
            CommissionRecord.period_month == month
        ).all()
        total_com = sum(c.total_commission for c in comms_current)
        pending_com = sum(c.total_commission for c in comms_current if c.approval_status == ApprovalStatus.PENDING)
        approved_com = sum(c.total_commission for c in comms_current if c.approval_status == ApprovalStatus.APPROVED)

        import math
        q = math.ceil(month / 3)
        rebates = self.db.query(RebateRecord).filter(
            RebateRecord.period_year == year,
            RebateRecord.period_quarter == q
        ).all()
        total_rbt = sum(r.total_rebate for r in rebates)
        frozen_rbt = sum(r.total_rebate for r in rebates if r.is_frozen)
        warn_count = sum(1 for r in rebates if r.status == RebateStatus.WARNING)

        pending_approvals = self.db.query(CommissionRecord).filter(
            CommissionRecord.approval_status.in_([ApprovalStatus.PENDING, ApprovalStatus.ESCALATED])
        ).count()

        sp_count = self.db.query(Salesperson).filter(Salesperson.is_active == True).count()
        partner_count = self.db.query(ChannelPartner).filter(ChannelPartner.is_active == True).count()

        recent_payments = self.db.query(PaymentInstruction).filter(
            PaymentInstruction.status == "pending"
        ).count()

        return {
            "current_period": f"{year}-{month:02d}",
            "current_quarter": f"{year} Q{q}",
            "commission": {
                "total_current_month": round(total_com, 2),
                "pending": round(pending_com, 2),
                "approved": round(approved_com, 2)
            },
            "rebate": {
                "total_current_quarter": round(total_rbt, 2),
                "frozen_amount": round(frozen_rbt, 2),
                "warning_count": warn_count
            },
            "workflow": {
                "pending_approvals": pending_approvals,
                "pending_payments": recent_payments
            },
            "overview": {
                "active_salespersons": sp_count,
                "active_partners": partner_count
            }
        }
