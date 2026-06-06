from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.models import (
    CommissionRecord, RebateRecord, ApprovalRecord, ApprovalStatus,
    PaymentInstruction, User, UserRole, Salesperson, ChannelPartner,
    AuditLog, LogAction, RebateStatus
)
from config import settings
import json


class ApprovalService:
    """多级审批工作流 - 自动触发、超10万区域总监审批、财务推送"""

    def __init__(self, db: Session):
        self.db = db
        self.threshold = settings.COMMISSION_APPROVAL_THRESHOLD

    def _log_action(self, user_id: int, username: str, action: LogAction,
                    entity_type: str, entity_id: Optional[int] = None,
                    entity_code: Optional[str] = None, details: Optional[str] = None):
        log = AuditLog(
            user_id=user_id, username=username, action=action,
            entity_type=entity_type, entity_id=entity_id, entity_code=entity_code,
            details=details
        )
        self.db.add(log)

    def _get_approver_for_level(self, level: int, salesperson: Salesperson = None,
                                 region: str = None) -> Optional[User]:
        """根据审批级别获取审批人"""
        if level == 1:
            if salesperson and salesperson.user and salesperson.user.manager_id:
                return self.db.query(User).filter(User.id == salesperson.user.manager_id).first()
            managers = self.db.query(User).filter(User.role == UserRole.SALES_MANAGER).first()
            return managers
        elif level == 2:
            directors = self.db.query(User).filter(User.role == UserRole.REGION_DIRECTOR)
            if region:
                directors = directors.filter(User.region == region)
            return directors.first()
        elif level == 3:
            return self.db.query(User).filter(User.role == UserRole.FINANCE).first()
        return None

    def trigger_commission_approval(self, record_id: int, user_id: int = None,
                                     username: str = None) -> Optional[CommissionRecord]:
        """触发佣金审批流程"""
        record = self.db.query(CommissionRecord).filter(
            CommissionRecord.id == record_id
        ).first()
        if not record:
            return None

        total = record.total_commission
        region = None
        salesperson = None
        if record.salesperson:
            salesperson = record.salesperson
            region = salesperson.region

        if total > self.threshold:
            record.approval_level = 2
            approver = self._get_approver_for_level(2, salesperson, region)
            record.approval_status = ApprovalStatus.ESCALATED
        else:
            record.approval_level = 1
            approver = self._get_approver_for_level(1, salesperson, region)
            record.approval_status = ApprovalStatus.PENDING

        if approver:
            record.current_approver_id = approver.id

        approval = ApprovalRecord(
            approval_type="commission",
            target_id=record.id,
            target_code=record.record_code,
            approver_id=approver.id if approver else (user_id or 1),
            approval_level=record.approval_level,
            action=ApprovalStatus.PENDING,
            comments=f"审批流程自动启动，金额: {total:.2f}"
        )
        self.db.add(approval)

        if user_id:
            self._log_action(user_id, username or "system", LogAction.SUBMIT,
                            "commission", record.id, record.record_code,
                            f"提交审批, 级别: {record.approval_level}")

        self.db.commit()
        self.db.refresh(record)
        return record

    def approve_commission(self, record_id: int, approver_id: int,
                            approver_name: str, comments: str = None) -> Optional[CommissionRecord]:
        """审批佣金记录"""
        record = self.db.query(CommissionRecord).filter(
            CommissionRecord.id == record_id
        ).first()
        if not record:
            return None

        region = record.salesperson.region if record.salesperson else None

        if record.approval_level == 1 and record.total_commission > self.threshold:
            record.approval_level = 2
            record.approval_status = ApprovalStatus.ESCALATED
            next_approver = self._get_approver_for_level(2, record.salesperson, region)
            if next_approver:
                record.current_approver_id = next_approver.id
        elif record.approval_level >= 2:
            record.approval_level += 1
            if record.approval_level > 3:
                record.approval_status = ApprovalStatus.APPROVED
                record.current_approver_id = None
                self._push_to_finance_commission(record, approver_id, approver_name)
            else:
                record.approval_status = ApprovalStatus.ESCALATED
                next_approver = self._get_approver_for_level(record.approval_level, record.salesperson, region)
                if next_approver:
                    record.current_approver_id = next_approver.id
        else:
            record.approval_status = ApprovalStatus.APPROVED
            record.current_approver_id = None
            self._push_to_finance_commission(record, approver_id, approver_name)

        approval = ApprovalRecord(
            approval_type="commission",
            target_id=record.id,
            target_code=record.record_code,
            approver_id=approver_id,
            approval_level=record.approval_level,
            action=ApprovalStatus.APPROVED,
            comments=comments or "审批通过"
        )
        self.db.add(approval)

        self._log_action(approver_id, approver_name, LogAction.APPROVE,
                        "commission", record.id, record.record_code,
                        comments or "审批通过")
        self.db.commit()
        self.db.refresh(record)
        return record

    def reject_commission(self, record_id: int, approver_id: int,
                           approver_name: str, comments: str = None) -> Optional[CommissionRecord]:
        """驳回佣金记录"""
        record = self.db.query(CommissionRecord).filter(
            CommissionRecord.id == record_id
        ).first()
        if not record:
            return None

        record.approval_status = ApprovalStatus.REJECTED
        record.current_approver_id = None

        approval = ApprovalRecord(
            approval_type="commission",
            target_id=record.id,
            target_code=record.record_code,
            approver_id=approver_id,
            approval_level=record.approval_level,
            action=ApprovalStatus.REJECTED,
            comments=comments or "审批驳回"
        )
        self.db.add(approval)

        self._log_action(approver_id, approver_name, LogAction.REJECT,
                        "commission", record.id, record.record_code,
                        comments or "审批驳回")
        self.db.commit()
        self.db.refresh(record)
        return record

    def _push_to_finance_commission(self, record: CommissionRecord, user_id: int, username: str):
        """推送至财务生成付款指令"""
        payee_name = record.salesperson.user.full_name if record.salesperson and record.salesperson.user else "未知"

        instruction = PaymentInstruction(
            instruction_code=f"PAY{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{record.id:06d}",
            payment_type="commission",
            target_id=record.id,
            target_code=record.record_code,
            payee_name=payee_name,
            amount=record.total_commission,
            status="pending",
            pushed_to_finance_at=datetime.utcnow(),
            remarks=f"佣金付款 - 周期 {record.period_year}-{record.period_month:02d}"
        )
        self.db.add(instruction)
        record.is_paid = False

        self._log_action(user_id, username, LogAction.SUBMIT,
                        "payment_instruction", entity_code=instruction.instruction_code,
                        details=f"佣金付款指令推送财务，金额: {record.total_commission:.2f}")

    def trigger_rebate_approval(self, record_id: int, user_id: int = None,
                                 username: str = None) -> Optional[RebateRecord]:
        """触发返利审批流程"""
        record = self.db.query(RebateRecord).filter(RebateRecord.id == record_id).first()
        if not record or record.is_frozen:
            return record

        record.approval_status = ApprovalStatus.PENDING
        approver = self._get_approver_for_level(3)
        if approver:
            approval = ApprovalRecord(
                approval_type="rebate",
                target_id=record.id,
                target_code=record.record_code,
                approver_id=approver.id,
                approval_level=3,
                action=ApprovalStatus.PENDING,
                comments=f"返利审批启动，金额: {record.total_rebate:.2f}"
            )
            self.db.add(approval)

        if user_id:
            self._log_action(user_id, username or "system", LogAction.SUBMIT,
                            "rebate", record.id, record.record_code,
                            "提交返利审批")

        self.db.commit()
        self.db.refresh(record)
        return record

    def approve_rebate(self, record_id: int, approver_id: int,
                        approver_name: str, comments: str = None) -> Optional[RebateRecord]:
        """审批返利记录"""
        record = self.db.query(RebateRecord).filter(RebateRecord.id == record_id).first()
        if not record:
            return None

        record.approval_status = ApprovalStatus.APPROVED
        record.status = RebateStatus.APPROVED

        approval = ApprovalRecord(
            approval_type="rebate",
            target_id=record.id,
            target_code=record.record_code,
            approver_id=approver_id,
            approval_level=3,
            action=ApprovalStatus.APPROVED,
            comments=comments or "返利审批通过"
        )
        self.db.add(approval)

        if not record.is_frozen:
            self._push_to_finance_rebate(record, approver_id, approver_name)

        self._log_action(approver_id, approver_name, LogAction.APPROVE,
                        "rebate", record.id, record.record_code,
                        comments or "审批通过")
        self.db.commit()
        self.db.refresh(record)
        return record

    def reject_rebate(self, record_id: int, approver_id: int,
                       approver_name: str, comments: str = None) -> Optional[RebateRecord]:
        """驳回返利记录"""
        record = self.db.query(RebateRecord).filter(RebateRecord.id == record_id).first()
        if not record:
            return None

        record.approval_status = ApprovalStatus.REJECTED

        approval = ApprovalRecord(
            approval_type="rebate",
            target_id=record.id,
            target_code=record.record_code,
            approver_id=approver_id,
            approval_level=3,
            action=ApprovalStatus.REJECTED,
            comments=comments or "返利审批驳回"
        )
        self.db.add(approval)

        self._log_action(approver_id, approver_name, LogAction.REJECT,
                        "rebate", record.id, record.record_code,
                        comments or "审批驳回")
        self.db.commit()
        self.db.refresh(record)
        return record

    def _push_to_finance_rebate(self, record: RebateRecord, user_id: int, username: str):
        """推送返利至财务生成付款指令"""
        partner = record.channel_partner
        instruction = PaymentInstruction(
            instruction_code=f"PAYRBT{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{record.id:06d}",
            payment_type="rebate",
            target_id=record.id,
            target_code=record.record_code,
            payee_name=partner.partner_name if partner else "未知渠道商",
            amount=record.total_rebate,
            status="pending",
            pushed_to_finance_at=datetime.utcnow(),
            remarks=f"渠道返利付款 - {record.period_year} Q{record.period_quarter}"
        )
        self.db.add(instruction)

        self._log_action(user_id, username, LogAction.SUBMIT,
                        "payment_instruction", entity_code=instruction.instruction_code,
                        details=f"返利付款指令推送财务，金额: {record.total_rebate:.2f}")

    def get_pending_approvals(self, user_id: int, role: UserRole) -> Dict:
        """获取待审批列表"""
        commissions = self.db.query(CommissionRecord).filter(
            CommissionRecord.current_approver_id == user_id,
            CommissionRecord.approval_status.in_([ApprovalStatus.PENDING, ApprovalStatus.ESCALATED])
        ).all()

        rebates = []
        if role in [UserRole.FINANCE, UserRole.ADMIN]:
            rebates = self.db.query(RebateRecord).filter(
                RebateRecord.approval_status == ApprovalStatus.PENDING,
                RebateRecord.is_frozen == False
            ).all()

        return {
            "commissions": [self._serialize_commission(r) for r in commissions],
            "rebates": [self._serialize_rebate(r) for r in rebates],
            "total_count": len(commissions) + len(rebates)
        }

    def _serialize_commission(self, r: CommissionRecord) -> Dict:
        return {
            "id": r.id, "code": r.record_code,
            "salesperson": r.salesperson.user.full_name if r.salesperson and r.salesperson.user else "未知",
            "period": f"{r.period_year}-{r.period_month:02d}",
            "amount": r.total_commission,
            "status": r.approval_status.value,
            "level": r.approval_level
        }

    def _serialize_rebate(self, r: RebateRecord) -> Dict:
        return {
            "id": r.id, "code": r.record_code,
            "partner": r.channel_partner.partner_name if r.channel_partner else "未知",
            "period": f"{r.period_year} Q{r.period_quarter}",
            "amount": r.total_rebate,
            "status": r.status.value,
            "frozen": r.is_frozen
        }
