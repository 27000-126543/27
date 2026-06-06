from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.models import (
    Appeal, AppealStatus, CommissionRecord, RebateRecord,
    SalesOrder, OrderItem, AuditLog, LogAction, User
)
from app.services.commission_calculator import CommissionService
import json


class AppealService:
    """异议申诉系统 - 在线申诉、订单关联、复核修正重算"""

    def __init__(self, db: Session):
        self.db = db

    def _log_action(self, user_id: int, username: str, action: LogAction,
                    entity_type: str, entity_id: Optional[int] = None,
                    entity_code: Optional[str] = None, details: Optional[str] = None):
        log = AuditLog(
            user_id=user_id, username=username, action=action,
            entity_type=entity_type, entity_id=entity_id, entity_code=entity_code,
            details=details
        )
        self.db.add(log)

    def submit_appeal(self, appellant_id: int, appellant_name: str,
                      appeal_type: str, reason: str,
                      commission_record_id: int = None,
                      rebate_record_id: int = None,
                      evidence: str = None) -> Appeal:
        """提交异议申诉"""
        appeal_code = f"APL{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        appellant_type = "salesperson"
        if rebate_record_id:
            appellant_type = "channel_partner"

        appeal = Appeal(
            appeal_code=appeal_code,
            appellant_id=appellant_id,
            appellant_type=appellant_type,
            commission_record_id=commission_record_id,
            rebate_record_id=rebate_record_id,
            appeal_type=appeal_type,
            reason=reason,
            evidence=evidence,
            status=AppealStatus.SUBMITTED
        )
        self.db.add(appeal)
        self.db.flush()

        self._log_action(appellant_id, appellant_name, LogAction.SUBMIT,
                        "appeal", appeal.id, appeal.appeal_code,
                        f"申诉类型: {appeal_type}")
        self.db.commit()
        self.db.refresh(appeal)
        return appeal

    def get_appeal_related_data(self, appeal_id: int) -> Dict:
        """获取申诉关联的订单交易数据供审批复核"""
        appeal = self.db.query(Appeal).filter(Appeal.id == appeal_id).first()
        if not appeal:
            return {}

        result = {
            "appeal": {
                "id": appeal.id, "code": appeal.appeal_code,
                "type": appeal.appeal_type, "reason": appeal.reason,
                "status": appeal.status.value, "evidence": appeal.evidence,
                "appellant": appeal.appellant.full_name if appeal.appellant else None,
                "created_at": appeal.created_at.isoformat() if appeal.created_at else None
            },
            "orders": []
        }

        if appeal.commission_record:
            record = appeal.commission_record
            result["commission_record"] = {
                "id": record.id, "code": record.record_code,
                "period": f"{record.period_year}-{record.period_month:02d}",
                "base_amount": record.base_amount,
                "commission_rate": record.commission_rate,
                "base_commission": record.base_commission,
                "bonus_amount": record.bonus_amount,
                "total_commission": record.total_commission,
                "category": record.product_category.value if record.product_category else None,
                "customer_level": record.customer_level.value if record.customer_level else None
            }

            if record.order:
                order = record.order
                items = []
                for item in order.items:
                    items.append({
                        "product": item.product.product_name if item.product else None,
                        "category": item.product.category.value if item.product and item.product.category else None,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                        "discount_rate": item.discount_rate,
                        "line_amount": item.line_amount
                    })
                result["orders"].append({
                    "order_number": order.order_number,
                    "order_date": order.order_date.isoformat() if order.order_date else None,
                    "customer": order.customer.customer_name if order.customer else None,
                    "customer_level": order.customer.level.value if order.customer and order.customer.level else None,
                    "total_amount": order.total_amount,
                    "net_amount": order.net_amount,
                    "paid_amount": order.paid_amount,
                    "payment_status": order.payment_status,
                    "items": items
                })

        if appeal.rebate_record:
            record = appeal.rebate_record
            result["rebate_record"] = {
                "id": record.id, "code": record.record_code,
                "period": f"{record.period_year} Q{record.period_quarter}",
                "total_sales": record.total_sales,
                "contract_ratio": record.contract_ratio,
                "adjusted_sales": record.adjusted_sales,
                "rebate_rate": record.rebate_rate,
                "base_rebate": record.base_rebate,
                "bonus_rebate": record.bonus_rebate,
                "total_rebate": record.total_rebate,
                "budget_amount": record.budget_amount,
                "budget_utilization": record.budget_utilization,
                "is_frozen": record.is_frozen
            }

            from app.services.rebate_calculator import RebateService
            q_start, q_end = RebateService(self.db)._get_quarter_range(record.period_year, record.period_quarter)
            orders = self.db.query(SalesOrder).filter(
                SalesOrder.channel_partner_id == record.channel_partner_id,
                SalesOrder.order_date >= q_start,
                SalesOrder.order_date < q_end
            ).all()
            for order in orders:
                items = []
                for item in order.items:
                    items.append({
                        "product": item.product.product_name if item.product else None,
                        "quantity": item.quantity,
                        "line_amount": item.line_amount
                    })
                result["orders"].append({
                    "order_number": order.order_number,
                    "order_date": order.order_date.isoformat() if order.order_date else None,
                    "customer": order.customer.customer_name if order.customer else None,
                    "net_amount": order.net_amount,
                    "items": items
                })

        return result

    def review_appeal(self, appeal_id: int, reviewer_id: int, reviewer_name: str,
                      approved: bool, review_comments: str,
                      correction_details: Dict = None) -> Optional[Appeal]:
        """复核申诉 - 通过则自动修正并重算"""
        appeal = self.db.query(Appeal).filter(Appeal.id == appeal_id).first()
        if not appeal:
            return None

        appeal.reviewer_id = reviewer_id
        appeal.review_comments = review_comments
        appeal.review_date = datetime.utcnow()

        if approved:
            appeal.status = AppealStatus.APPROVED
            appeal.is_resolved = True

            if appeal.commission_record_id:
                comm_service = CommissionService(self.db)
                new_record = comm_service.recalculate_record(
                    appeal.commission_record_id, reviewer_id, reviewer_name
                )
                if new_record:
                    appeal.resolution_notes = f"已重算，新佣金记录: {new_record.record_code}，金额: {new_record.total_commission:.2f}"

            if appeal.rebate_record_id:
                from app.services.rebate_calculator import RebateService
                rb = RebateService(self.db)
                record = self.db.query(RebateRecord).filter(
                    RebateRecord.id == appeal.rebate_record_id
                ).first()
                if record:
                    new_record = rb._calculate_partner_rebate(
                        record.channel_partner, record.period_year, record.period_quarter, force=True
                    )
                    if new_record:
                        self.db.commit()
                        appeal.resolution_notes = f"已重算渠道返利，新金额: {new_record.total_rebate:.2f}"
        else:
            appeal.status = AppealStatus.REJECTED
            appeal.is_resolved = True
            appeal.resolution_notes = review_comments

        self._log_action(reviewer_id, reviewer_name,
                        LogAction.APPROVE if approved else LogAction.REJECT,
                        "appeal", appeal.id, appeal.appeal_code,
                        review_comments)
        self.db.commit()
        self.db.refresh(appeal)
        return appeal

    def get_user_appeals(self, appellant_id: int, status: AppealStatus = None) -> List[Dict]:
        """获取用户的申诉列表"""
        query = self.db.query(Appeal).filter(Appeal.appellant_id == appellant_id)
        if status:
            query = query.filter(Appeal.status == status)
        appeals = query.order_by(Appeal.created_at.desc()).all()
        return [
            {
                "id": a.id, "code": a.appeal_code,
                "type": a.appeal_type, "reason": a.reason[:100],
                "status": a.status.value,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "review_comments": a.review_comments,
                "is_resolved": a.is_resolved
            }
            for a in appeals
        ]

    def get_pending_reviews(self) -> List[Dict]:
        """获取待复核的申诉列表"""
        appeals = self.db.query(Appeal).filter(
            Appeal.status.in_([AppealStatus.SUBMITTED, AppealStatus.UNDER_REVIEW])
        ).order_by(Appeal.created_at.desc()).all()
        return [
            {
                "id": a.id, "code": a.appeal_code,
                "type": a.appeal_type, "reason": a.reason[:100],
                "appellant": a.appellant.full_name if a.appellant else None,
                "status": a.status.value,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in appeals
        ]
