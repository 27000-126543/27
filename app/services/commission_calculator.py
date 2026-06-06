from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.models import (
    CommissionRecord, SalesOrder, OrderItem, Product, Salesperson, Customer,
    CommissionTierRule, BonusRule, ApprovalStatus, AuditLog, LogAction,
    ProductCategory, CustomerLevel
)
from config import settings
import json


class CommissionService:
    """佣金计算引擎 - 按产品类别、客户等级、合同金额、阶梯奖励计算"""

    def __init__(self, db: Session):
        self.db = db

    def _log_action(self, user_id: int, username: str, action: LogAction,
                    entity_type: str, entity_id: Optional[int] = None,
                    entity_code: Optional[str] = None, details: Optional[str] = None):
        log = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_code=entity_code,
            details=details
        )
        self.db.add(log)

    def _get_applicable_tier_rule(self, product_category: ProductCategory,
                                   customer_level: CustomerLevel,
                                   amount: float,
                                   calc_date: date) -> Optional[CommissionTierRule]:
        """获取适用的阶梯佣金规则"""
        rules = self.db.query(CommissionTierRule).filter(
            CommissionTierRule.is_active == True,
            CommissionTierRule.effective_from <= calc_date,
            and_(
                (CommissionTierRule.effective_to.is_(None)) |
                (CommissionTierRule.effective_to >= calc_date)
            )
        ).order_by(CommissionTierRule.priority.desc()).all()

        best_rule = None
        for rule in rules:
            if rule.product_category and rule.product_category != product_category:
                continue
            if rule.customer_level and rule.customer_level != customer_level:
                continue
            if amount < rule.min_amount:
                continue
            if rule.max_amount is not None and amount >= rule.max_amount:
                continue
            if best_rule is None or rule.priority > best_rule.priority:
                best_rule = rule
        return best_rule

    def _calculate_order_commission(self, order: SalesOrder,
                                     period_year: int, period_month: int) -> List[CommissionRecord]:
        """计算单个订单的佣金（按产品类别分拆）"""
        records = []
        category_amounts: Dict[ProductCategory, float] = {}

        for item in order.items:
            product = item.product
            if product.category not in category_amounts:
                category_amounts[product.category] = 0.0
            category_amounts[product.category] += item.line_amount

        for category, base_amount in category_amounts.items():
            customer_level = order.customer.level if order.customer else CustomerLevel.NORMAL
            calc_date = order.order_date

            tier_rule = self._get_applicable_tier_rule(category, customer_level, base_amount, calc_date)

            salesperson = order.salesperson
            if tier_rule:
                rate = tier_rule.base_rate
            elif salesperson and salesperson.base_commission_rate:
                rate = salesperson.base_commission_rate
            else:
                rate = 0.02

            base_commission = round(base_amount * rate, 2)

            bonus = 0.0
            if tier_rule and tier_rule.bonus_rate > 0:
                bonus = round(base_amount * tier_rule.bonus_rate, 2)

            total = round(base_commission + bonus, 2)

            record_code = f"COM{period_year}{period_month:02d}{order.salesperson_id:05d}{order.id:06d}{category.value[:3].upper()}"

            details = json.dumps({
                "rule_id": tier_rule.id if tier_rule else None,
                "rule_name": tier_rule.name if tier_rule else "default",
                "base_rate": rate,
                "tier_bonus_rate": tier_rule.bonus_rate if tier_rule else 0,
                "order_number": order.order_number,
                "customer_level": customer_level.value,
                "product_category": category.value
            }, ensure_ascii=False)

            record = CommissionRecord(
                record_code=record_code,
                salesperson_id=order.salesperson_id,
                period_year=period_year,
                period_month=period_month,
                order_id=order.id,
                product_category=category,
                customer_level=customer_level,
                base_amount=base_amount,
                commission_rate=rate,
                base_commission=base_commission,
                bonus_amount=bonus,
                total_commission=total,
                calculation_details=details,
                approval_status=ApprovalStatus.PENDING
            )
            records.append(record)

        return records

    def _calculate_monthly_bonus(self, salesperson_id: int, period_year: int,
                                  period_month: int, total_base: float) -> float:
        """计算月度超额回款等阶梯奖励"""
        bonus = 0.0
        bonus_rules = self.db.query(BonusRule).filter(
            BonusRule.is_active == True,
            BonusRule.period == "monthly"
        ).all()

        for rule in bonus_rules:
            if rule.rule_type == "collection_over_quota":
                if total_base >= rule.threshold_amount:
                    if rule.bonus_percentage > 0:
                        bonus += round(total_base * rule.bonus_percentage, 2)
                    elif rule.bonus_amount > 0:
                        bonus += rule.bonus_amount
        return round(bonus, 2)

    def calculate_monthly_commission(self, period_year: int, period_month: int,
                                     force_recalculate: bool = False,
                                     user_id: int = None, username: str = None) -> Dict:
        """计算月度佣金（核心方法）"""
        result = {
            "period": f"{period_year}-{period_month:02d}",
            "processed_orders": 0,
            "created_records": 0,
            "skipped_records": 0,
            "total_amount": 0.0,
            "salespersons": 0
        }

        month_start = date(period_year, period_month, 1)
        if period_month == 12:
            month_end = date(period_year + 1, 1, 1)
        else:
            month_end = date(period_year, period_month + 1, 1)

        orders = self.db.query(SalesOrder).filter(
            SalesOrder.order_date >= month_start,
            SalesOrder.order_date < month_end,
            SalesOrder.is_active == True
        ).all()

        salesperson_totals: Dict[int, Dict] = {}

        for order in orders:
            if not order.salesperson_id:
                continue
            result["processed_orders"] += 1

            existing_count = self.db.query(func.count(CommissionRecord.id)).filter(
                CommissionRecord.salesperson_id == order.salesperson_id,
                CommissionRecord.period_year == period_year,
                CommissionRecord.period_month == period_month,
                CommissionRecord.order_id == order.id,
                CommissionRecord.is_corrected == False
            ).scalar() or 0

            if existing_count > 0 and not force_recalculate:
                result["skipped_records"] += 1
                existing_records = self.db.query(CommissionRecord).filter(
                    CommissionRecord.salesperson_id == order.salesperson_id,
                    CommissionRecord.period_year == period_year,
                    CommissionRecord.period_month == period_month,
                    CommissionRecord.order_id == order.id,
                    CommissionRecord.is_corrected == False
                ).all()
                if order.salesperson_id not in salesperson_totals:
                    salesperson_totals[order.salesperson_id] = {"base": 0.0, "bonus": 0.0, "records": []}
                for rec in existing_records:
                    salesperson_totals[order.salesperson_id]["base"] += rec.total_commission
                continue

            if existing_count > 0 and force_recalculate:
                for rec in self.db.query(CommissionRecord).filter(
                    CommissionRecord.salesperson_id == order.salesperson_id,
                    CommissionRecord.period_year == period_year,
                    CommissionRecord.period_month == period_month,
                    CommissionRecord.order_id == order.id
                ).all():
                    self.db.delete(rec)
                self.db.flush()

            order_records = self._calculate_order_commission(order, period_year, period_month)
            for rec in order_records:
                if self.check_duplicate(
                    rec.salesperson_id, rec.period_year, rec.period_month,
                    rec.order_id, rec.product_category
                ):
                    continue
                self.db.add(rec)
                result["created_records"] += 1
                result["total_amount"] += rec.total_commission

                if rec.salesperson_id not in salesperson_totals:
                    salesperson_totals[rec.salesperson_id] = {"base": 0.0, "bonus": 0.0, "records": []}
                salesperson_totals[rec.salesperson_id]["base"] += rec.total_commission
                salesperson_totals[rec.salesperson_id]["records"].append(rec)

        self.db.flush()

        for sp_id, data in salesperson_totals.items():
            result["salespersons"] += 1
            monthly_bonus = self._calculate_monthly_bonus(sp_id, period_year, period_month, data["base"])
            if monthly_bonus > 0 and data["records"]:
                bonus_rec = data["records"][0]
                bonus_rec.bonus_amount += monthly_bonus
                bonus_rec.total_commission += monthly_bonus
                result["total_amount"] += monthly_bonus
                details = json.loads(bonus_rec.calculation_details or "{}")
                details["monthly_bonus"] = monthly_bonus
                bonus_rec.calculation_details = json.dumps(details, ensure_ascii=False)

        self.db.commit()

        if user_id:
            self._log_action(user_id, username or "system", LogAction.CALCULATE,
                            "commission", details=json.dumps(result, ensure_ascii=False))

        return result

    def check_duplicate(self, salesperson_id: int, period_year: int,
                        period_month: int, order_id: int,
                        product_category: str = None) -> bool:
        """校验历史记录防止重复计算"""
        query = self.db.query(CommissionRecord).filter(
            CommissionRecord.salesperson_id == salesperson_id,
            CommissionRecord.period_year == period_year,
            CommissionRecord.period_month == period_month,
            CommissionRecord.order_id == order_id,
            CommissionRecord.is_corrected == False
        )
        if product_category:
            query = query.filter(CommissionRecord.product_category == product_category)
        existing = query.first()
        return existing is not None

    def recalculate_record(self, record_id: int, user_id: int,
                            username: str) -> Optional[CommissionRecord]:
        """复核后修正并重算单条佣金记录"""
        import uuid
        record = self.db.query(CommissionRecord).filter(
            CommissionRecord.id == record_id
        ).first()
        if not record:
            return None

        if not record.order:
            return None

        record.is_corrected = True
        self.db.flush()

        new_records = self._calculate_order_commission(record.order, record.period_year, record.period_month)
        for nr in new_records:
            if nr.product_category != record.product_category:
                continue

            nr.original_record_id = record.id
            nr.approval_status = ApprovalStatus.PENDING
            nr.remarks = f"修正自记录 {record.record_code}"
            unique_suffix = uuid.uuid4().hex[:8].upper()
            nr.record_code = f"{record.record_code}R{unique_suffix}"
            self.db.add(nr)

            self._log_action(user_id, username, LogAction.RECALCULATE,
                            "commission", record.id, record.record_code,
                            f"原金额:{record.total_commission},新金额:{nr.total_commission},原记录已标记is_corrected=True")
            self.db.commit()
            self.db.refresh(nr)
            return nr
        return None

    def get_commission_summary(self, period_year: int, period_month: int,
                                salesperson_id: int = None,
                                region: str = None) -> Dict:
        """获取佣金汇总数据"""
        query = self.db.query(CommissionRecord).filter(
            CommissionRecord.period_year == period_year,
            CommissionRecord.period_month == period_month
        )
        if salesperson_id:
            query = query.filter(CommissionRecord.salesperson_id == salesperson_id)
        if region:
            query = query.join(Salesperson).filter(Salesperson.region == region)

        records = query.all()
        total = sum(r.total_commission for r in records)
        by_category: Dict[str, float] = {}
        by_salesperson: Dict[int, float] = {}

        for r in records:
            cat = r.product_category.value if r.product_category else "unknown"
            by_category[cat] = by_category.get(cat, 0) + r.total_commission
            by_salesperson[r.salesperson_id] = by_salesperson.get(r.salesperson_id, 0) + r.total_commission

        return {
            "period": f"{period_year}-{period_month:02d}",
            "total_commission": round(total, 2),
            "record_count": len(records),
            "salesperson_count": len(by_salesperson),
            "by_category": by_category,
            "by_salesperson_avg": round(total / len(by_salesperson), 2) if by_salesperson else 0
        }
