from datetime import datetime, date
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.models import (
    RebateRecord, SalesOrder, ChannelPartner, Product,
    RebateTierRule, RebateStatus, ApprovalStatus, AuditLog, LogAction
)
import json
from dateutil.relativedelta import relativedelta


class RebateService:
    """渠道返利计算 - 按季度累计销售额和合同比例计算，超预算预警冻结"""

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

    def _get_quarter_range(self, year: int, quarter: int) -> tuple:
        start_month = (quarter - 1) * 3 + 1
        start = date(year, start_month, 1)
        if quarter == 4:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, start_month + 3, 1)
        return start, end

    def _get_applicable_tier_rule(self, partner: ChannelPartner,
                                   amount: float) -> Optional[RebateTierRule]:
        """获取适用的阶梯返利规则"""
        rules = self.db.query(RebateTierRule).filter(
            RebateTierRule.is_active == True
        ).order_by(RebateTierRule.priority.desc()).all()

        best_rule = None
        for rule in rules:
            if rule.tier and rule.tier != partner.tier:
                continue
            if amount < rule.min_amount:
                continue
            if rule.max_amount is not None and amount >= rule.max_amount:
                continue
            if best_rule is None or rule.priority > best_rule.priority:
                best_rule = rule
        return best_rule

    def _calculate_partner_rebate(self, partner: ChannelPartner,
                                   period_year: int, period_quarter: int,
                                   force: bool = False) -> Optional[RebateRecord]:
        """计算单个渠道商的季度返利"""
        q_start, q_end = self._get_quarter_range(period_year, period_quarter)

        existing = self.db.query(RebateRecord).filter(
            RebateRecord.channel_partner_id == partner.id,
            RebateRecord.period_year == period_year,
            RebateRecord.period_quarter == period_quarter
        ).first()

        if existing and not force:
            return None

        orders = self.db.query(SalesOrder).filter(
            SalesOrder.channel_partner_id == partner.id,
            SalesOrder.order_date >= q_start,
            SalesOrder.order_date < q_end,
            SalesOrder.is_active == True
        ).all()

        total_sales = sum(o.net_amount for o in orders)
        contract_ratio = partner.contract_ratio or 1.0
        adjusted_sales = round(total_sales * contract_ratio, 2)

        tier_rule = self._get_applicable_tier_rule(partner, adjusted_sales)

        if tier_rule:
            rate = tier_rule.rebate_rate
            bonus_rate = tier_rule.bonus_rate
        else:
            rate = partner.base_rebate_rate or 0.03
            bonus_rate = 0.0

        base_rebate = round(adjusted_sales * rate, 2)
        bonus_rebate = round(adjusted_sales * bonus_rate, 2)
        total_rebate = round(base_rebate + bonus_rebate, 2)

        budget = partner.quarterly_budget or 0.0
        utilization = round((total_rebate / budget * 100), 2) if budget > 0 else 0.0

        status = RebateStatus.CALCULATED
        warning_msg = None
        is_frozen = False
        frozen_reason = None

        if budget > 0 and total_rebate > budget:
            status = RebateStatus.WARNING
            is_frozen = True
            warning_msg = f"返利金额 {total_rebate:.2f} 超出季度预算 {budget:.2f}，超额部分 {total_rebate - budget:.2f} 已冻结"
            frozen_reason = f"超出预算，预算利用率: {utilization:.1f}%"

        record_code = f"RBT{period_year}Q{period_quarter}{partner.id:05d}"

        details = json.dumps({
            "order_count": len(orders),
            "total_sales": total_sales,
            "contract_ratio": contract_ratio,
            "tier_rule_id": tier_rule.id if tier_rule else None,
            "tier_rule_name": tier_rule.name if tier_rule else "default",
            "rebate_rate": rate,
            "bonus_rate": bonus_rate,
            "budget": budget,
            "utilization_percent": utilization
        }, ensure_ascii=False)

        if existing:
            existing.total_sales = total_sales
            existing.contract_ratio = contract_ratio
            existing.adjusted_sales = adjusted_sales
            existing.rebate_rate = rate
            existing.base_rebate = base_rebate
            existing.bonus_rebate = bonus_rebate
            existing.total_rebate = total_rebate
            existing.budget_amount = budget
            existing.budget_utilization = utilization
            existing.status = status
            existing.warning_message = warning_msg
            existing.is_frozen = is_frozen
            existing.frozen_reason = frozen_reason
            existing.calculation_details = details
            record = existing
        else:
            record = RebateRecord(
                record_code=record_code,
                channel_partner_id=partner.id,
                period_year=period_year,
                period_quarter=period_quarter,
                total_sales=total_sales,
                contract_ratio=contract_ratio,
                adjusted_sales=adjusted_sales,
                rebate_rate=rate,
                base_rebate=base_rebate,
                bonus_rebate=bonus_rebate,
                total_rebate=total_rebate,
                budget_amount=budget,
                budget_utilization=utilization,
                status=status,
                warning_message=warning_msg,
                is_frozen=is_frozen,
                frozen_reason=frozen_reason,
                calculation_details=details
            )
            self.db.add(record)

        return record

    def calculate_quarterly_rebates(self, period_year: int, period_quarter: int,
                                    force_recalculate: bool = False,
                                    user_id: int = None, username: str = None) -> Dict:
        """计算季度渠道返利（核心方法）"""
        result = {
            "period": f"{period_year} Q{period_quarter}",
            "partners_processed": 0,
            "records_created": 0,
            "records_updated": 0,
            "skipped": 0,
            "total_rebate": 0.0,
            "warnings": 0,
            "frozen": 0
        }

        partners = self.db.query(ChannelPartner).filter(
            ChannelPartner.is_active == True
        ).all()

        for partner in partners:
            result["partners_processed"] += 1
            existing = self.db.query(RebateRecord).filter(
                RebateRecord.channel_partner_id == partner.id,
                RebateRecord.period_year == period_year,
                RebateRecord.period_quarter == period_quarter
            ).first()

            if existing and not force_recalculate:
                result["skipped"] += 1
                result["total_rebate"] += existing.total_rebate
                if existing.status == RebateStatus.WARNING:
                    result["warnings"] += 1
                if existing.is_frozen:
                    result["frozen"] += 1
                continue

            record = self._calculate_partner_rebate(partner, period_year, period_quarter, force_recalculate)
            if record:
                if existing:
                    result["records_updated"] += 1
                else:
                    result["records_created"] += 1
                result["total_rebate"] += record.total_rebate
                if record.status == RebateStatus.WARNING:
                    result["warnings"] += 1
                if record.is_frozen:
                    result["frozen"] += 1

        self.db.commit()

        if user_id:
            self._log_action(user_id, username or "system", LogAction.CALCULATE,
                            "rebate", details=json.dumps(result, ensure_ascii=False))

        return result

    def unfreeze_rebate(self, record_id: int, user_id: int, username: str,
                         reason: str = None) -> Optional[RebateRecord]:
        """解冻被冻结的超额返利"""
        record = self.db.query(RebateRecord).filter(RebateRecord.id == record_id).first()
        if not record:
            return None

        was_frozen = record.is_frozen
        record.is_frozen = False
        record.status = RebateStatus.APPROVED
        record.frozen_reason = None
        if reason:
            record.remarks = (record.remarks or "") + f"\n解冻原因: {reason}"

        self._log_action(user_id, username, LogAction.UNFREEZE,
                        "rebate", record.id, record.record_code,
                        reason or "人工审批解冻")
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_rebate_summary(self, period_year: int = None, period_quarter: int = None,
                            partner_id: int = None, region: str = None) -> Dict:
        """获取返利汇总数据"""
        query = self.db.query(RebateRecord)
        if period_year:
            query = query.filter(RebateRecord.period_year == period_year)
        if period_quarter:
            query = query.filter(RebateRecord.period_quarter == period_quarter)
        if partner_id:
            query = query.filter(RebateRecord.channel_partner_id == partner_id)
        if region:
            query = query.join(ChannelPartner).filter(ChannelPartner.region == region)

        records = query.all()
        total = sum(r.total_rebate for r in records)
        frozen = sum(r.total_rebate for r in records if r.is_frozen)
        warnings = [r for r in records if r.status == RebateStatus.WARNING]

        by_partner: Dict[int, float] = {}
        for r in records:
            by_partner[r.channel_partner_id] = by_partner.get(r.channel_partner_id, 0) + r.total_rebate

        return {
            "total_rebate": round(total, 2),
            "frozen_amount": round(frozen, 2),
            "warning_count": len(warnings),
            "partner_count": len(by_partner),
            "record_count": len(records),
            "avg_per_partner": round(total / len(by_partner), 2) if by_partner else 0
        }
