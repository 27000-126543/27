from datetime import datetime, date
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.models import (
    SalesOrder, OrderItem, Customer, Salesperson, ChannelPartner, Product,
    DataSyncLog, CustomerLevel, ProductCategory, AuditLog, LogAction
)
from app.database import get_db
import random
from datetime import timedelta


class DataSyncService:
    """数据抓取服务 - 从CRM和订单系统同步数据"""

    def __init__(self, db: Session):
        self.db = db

    def _log_sync(self, sync_type: str, source_system: str) -> DataSyncLog:
        log = DataSyncLog(
            sync_type=sync_type,
            source_system=source_system,
            status="running",
            started_at=datetime.utcnow()
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def _complete_sync(self, log: DataSyncLog, processed: int, succeeded: int,
                       failed: int, error: Optional[str] = None):
        log.records_processed = processed
        log.records_succeeded = succeeded
        log.records_failed = failed
        log.error_message = error
        log.status = "completed" if failed == 0 else "completed_with_errors"
        log.completed_at = datetime.utcnow()
        self.db.commit()

    def sync_from_crm(self, start_date: Optional[date] = None,
                      end_date: Optional[date] = None) -> Dict:
        """从CRM系统同步客户、销售人员、渠道商等基础数据"""
        log = self._log_sync("crm_base_data", "CRM")
        processed = 0
        succeeded = 0
        failed = 0

        try:
            customers = self._fetch_mock_customers(start_date, end_date)
            for c_data in customers:
                processed += 1
                try:
                    existing = self.db.query(Customer).filter(
                        Customer.customer_code == c_data["customer_code"]
                    ).first()
                    if existing:
                        for k, v in c_data.items():
                            setattr(existing, k, v)
                    else:
                        customer = Customer(**c_data)
                        self.db.add(customer)
                    succeeded += 1
                except Exception as e:
                    failed += 1

            persons = self._fetch_mock_salespersons()
            for p_data in persons:
                processed += 1
                try:
                    existing = self.db.query(Salesperson).filter(
                        Salesperson.salesperson_code == p_data["salesperson_code"]
                    ).first()
                    if existing:
                        for k, v in p_data.items():
                            if k != "user":
                                setattr(existing, k, v)
                    else:
                        sp = Salesperson(**p_data)
                        self.db.add(sp)
                    succeeded += 1
                except Exception as e:
                    failed += 1

            partners = self._fetch_mock_channel_partners()
            for p_data in partners:
                processed += 1
                try:
                    existing = self.db.query(ChannelPartner).filter(
                        ChannelPartner.partner_code == p_data["partner_code"]
                    ).first()
                    if existing:
                        for k, v in p_data.items():
                            setattr(existing, k, v)
                    else:
                        partner = ChannelPartner(**p_data)
                        self.db.add(partner)
                    succeeded += 1
                except Exception as e:
                    failed += 1

            products = self._fetch_mock_products()
            for p_data in products:
                processed += 1
                try:
                    existing = self.db.query(Product).filter(
                        Product.product_code == p_data["product_code"]
                    ).first()
                    if existing:
                        for k, v in p_data.items():
                            setattr(existing, k, v)
                    else:
                        product = Product(**p_data)
                        self.db.add(product)
                    succeeded += 1
                except Exception as e:
                    failed += 1

            self.db.commit()
            self._complete_sync(log, processed, succeeded, failed)

            return {
                "processed": processed,
                "succeeded": succeeded,
                "failed": failed,
                "customers": len(customers),
                "salespersons": len(persons),
                "partners": len(partners),
                "products": len(products)
            }
        except Exception as e:
            self._complete_sync(log, processed, succeeded, failed, str(e))
            raise

    def sync_from_order_system(self, start_date: Optional[date] = None,
                               end_date: Optional[date] = None) -> Dict:
        """从订单系统同步销售订单数据"""
        log = self._log_sync("sales_orders", "OrderSystem")
        processed = 0
        succeeded = 0
        failed = 0

        try:
            if not start_date:
                start_date = date.today().replace(day=1) - timedelta(days=60)
            if not end_date:
                end_date = date.today()

            orders = self._fetch_mock_orders(start_date, end_date)
            order_ids = []

            for o_data in orders:
                processed += 1
                try:
                    items_data = o_data.pop("items", [])
                    existing = self.db.query(SalesOrder).filter(
                        SalesOrder.order_number == o_data["order_number"]
                    ).first()
                    if existing:
                        for k, v in o_data.items():
                            setattr(existing, k, v)
                        existing.synced_at = datetime.utcnow()
                        order = existing
                        for item in existing.items:
                            self.db.delete(item)
                    else:
                        order = SalesOrder(**o_data, synced_at=datetime.utcnow())
                        self.db.add(order)

                    self.db.flush()

                    for item_data in items_data:
                        item = OrderItem(order_id=order.id, **item_data)
                        self.db.add(item)

                    succeeded += 1
                    order_ids.append(o_data["order_number"])
                except Exception as e:
                    failed += 1
                    self.db.rollback()

            self.db.commit()
            self._complete_sync(log, processed, succeeded, failed)

            return {
                "processed": processed,
                "succeeded": succeeded,
                "failed": failed,
                "order_numbers": order_ids
            }
        except Exception as e:
            self._complete_sync(log, processed, succeeded, failed, str(e))
            raise

    def _fetch_mock_customers(self, start_date, end_date) -> List[Dict]:
        customers = self.db.query(Customer).count()
        if customers > 0:
            return []
        return [
            {"customer_code": f"C{i:05d}", "customer_name": f"客户{i}科技有限公司",
             "level": random.choice(list(CustomerLevel)),
             "industry": random.choice(["金融", "制造", "零售", "互联网", "能源", "医疗"]),
             "region": random.choice(["华东", "华南", "华北", "西南", "西北", "东北"]),
             "contact_person": f"联系人{i}", "contact_email": f"contact{i}@test.com",
             "contact_phone": f"1380000{i:04d}", "channel_partner_id": None if i % 3 == 0 else (i % 10) + 1}
            for i in range(1, 51)
        ]

    def _fetch_mock_salespersons(self) -> List[Dict]:
        persons = self.db.query(Salesperson).count()
        if persons > 0:
            return []
        return [
            {"salesperson_code": f"SP{i:04d}", "tier": random.choice(["T1", "T2", "T3"]),
             "base_commission_rate": round(random.uniform(0.015, 0.035), 4),
             "quota": random.choice([500000, 800000, 1000000, 1500000, 2000000]),
             "region": random.choice(["华东", "华南", "华北", "西南"]),
             "user_id": i}
            for i in range(1, 31)
        ]

    def _fetch_mock_channel_partners(self) -> List[Dict]:
        partners = self.db.query(ChannelPartner).count()
        if partners > 0:
            return []
        return [
            {"partner_code": f"CP{i:03d}", "partner_name": f"渠道合作伙伴{i}",
             "tier": random.choice(["Platinum", "Gold", "Silver"]),
             "base_rebate_rate": round(random.uniform(0.02, 0.06), 4),
             "quarterly_budget": random.choice([200000, 500000, 800000, 1000000]),
             "annual_budget": random.choice([800000, 2000000, 3200000, 4000000]),
             "contract_start_date": date(2025, 1, 1),
             "contract_end_date": date(2026, 12, 31),
             "contract_ratio": round(random.uniform(0.8, 1.2), 2),
             "region": random.choice(["华东", "华南", "华北", "西南"]),
             "contact_person": f"渠道负责人{i}", "contact_email": f"channel{i}@test.com",
             "contact_phone": f"1390000{i:04d}"}
            for i in range(1, 21)
        ]

    def _fetch_mock_products(self) -> List[Dict]:
        products = self.db.query(Product).count()
        if products > 0:
            return []
        sample_products = [
            ("P001", "企业云服务器标准版", ProductCategory.CLOUD, 50000, 30000),
            ("P002", "企业云服务器高级版", ProductCategory.CLOUD, 120000, 70000),
            ("P003", "数据分析平台软件", ProductCategory.SOFTWARE, 200000, 80000),
            ("P004", "CRM客户管理系统", ProductCategory.SOFTWARE, 150000, 60000),
            ("P005", "硬件服务器设备", ProductCategory.HARDWARE, 80000, 55000),
            ("P006", "网络交换机设备", ProductCategory.HARDWARE, 35000, 22000),
            ("P007", "年度运维服务包", ProductCategory.SERVICE, 60000, 20000),
            ("P008", "数字化转型咨询", ProductCategory.CONSULTING, 300000, 100000),
            ("P009", "安全防护服务", ProductCategory.SERVICE, 90000, 35000),
            ("P010", "定制化开发服务", ProductCategory.SOFTWARE, 500000, 200000),
        ]
        return [
            {"product_code": code, "product_name": name, "category": cat,
             "unit_price": price, "cost": cost}
            for code, name, cat, price, cost in sample_products
        ]

    def _fetch_mock_orders(self, start_date: date, end_date: date) -> List[Dict]:
        from collections import OrderedDict
        existing_count = self.db.query(SalesOrder).count()
        if existing_count > 100:
            return []

        customers = self.db.query(Customer).all()
        salespersons = self.db.query(Salesperson).all()
        products = self.db.query(Product).all()
        partners = self.db.query(ChannelPartner).all()

        if not customers or not salespersons or not products:
            return []

        orders = []
        order_num = existing_count
        current = start_date

        while current <= end_date:
            if random.random() < 0.6:
                for _ in range(random.randint(1, 5)):
                    order_num += 1
                    customer = random.choice(customers)
                    salesperson = random.choice(salespersons)
                    partner = random.choice(partners) if random.random() < 0.4 and partners else None
                    num_items = random.randint(1, 4)
                    items = []
                    total = 0.0
                    for _ in range(num_items):
                        product = random.choice(products)
                        qty = random.randint(1, 20)
                        disc = round(random.uniform(0, 0.15), 2)
                        line = qty * product.unit_price * (1 - disc)
                        items.append({
                            "product_id": product.id,
                            "quantity": qty,
                            "unit_price": product.unit_price,
                            "discount_rate": disc,
                            "line_amount": line
                        })
                        total += line

                    discount = round(random.uniform(0, 0.05), 2) * total
                    net = total - discount
                    paid = net if random.random() < 0.7 else round(net * random.uniform(0.3, 0.9), 2)

                    orders.append({
                        "order_number": f"SO{current.strftime('%Y%m')}{order_num:06d}",
                        "order_date": current,
                        "customer_id": customer.id,
                        "salesperson_id": salesperson.id,
                        "channel_partner_id": partner.id if partner else None,
                        "total_amount": total,
                        "discount_amount": discount,
                        "net_amount": net,
                        "paid_amount": paid,
                        "payment_status": "paid" if paid >= net else ("partial" if paid > 0 else "unpaid"),
                        "contract_number": f"CT{current.strftime('%Y')}{order_num:05d}" if random.random() < 0.8 else None,
                        "region": salesperson.region,
                        "crm_id": f"CRM{order_num:06d}",
                        "order_system_id": f"ORD{order_num:06d}",
                        "items": items
                    })
            current += timedelta(days=1)

        return orders
