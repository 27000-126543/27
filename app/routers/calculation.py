from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from app.database import get_db
from app.auth import get_current_user, require_roles
from app.models import User, UserRole, CommissionTierRule, BonusRule, RebateTierRule
from app.services.data_sync import DataSyncService
from app.services.commission_calculator import CommissionService
from app.services.rebate_calculator import RebateService
from app.services.query_service import QueryService
from app.schemas import (
    CalculateCommissionRequest, CalculateRebateRequest,
    QueryCommissionRequest, QueryRebateRequest, GenericResponse,
    CommissionRecordOut, RebateRecordOut
)

router = APIRouter(prefix="/api/calculation", tags=["计算与查询"])


@router.post("/sync")
def sync_data(sync_type: str = Query("all", description="crm/order/all"),
              start_date: Optional[date] = None,
              end_date: Optional[date] = None,
              db: Session = Depends(get_db),
              current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SALES_MANAGER, UserRole.FINANCE))):
    sync = DataSyncService(db)
    result = {}
    if sync_type in ["crm", "all"]:
        result["crm"] = sync.sync_from_crm(start_date, end_date)
    if sync_type in ["order", "all"]:
        result["order"] = sync.sync_from_order_system(start_date, end_date)
    return GenericResponse(message="数据同步完成", data=result)


@router.post("/commission/calculate")
def calculate_commission(req: CalculateCommissionRequest,
                          db: Session = Depends(get_db),
                          current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SALES_MANAGER, UserRole.FINANCE))):
    calc = CommissionService(db)
    result = calc.calculate_monthly_commission(
        req.year, req.month, req.force_recalculate,
        current_user.id, current_user.username
    )
    return GenericResponse(message="佣金计算完成", data=result)


@router.post("/rebate/calculate")
def calculate_rebate(req: CalculateRebateRequest,
                      db: Session = Depends(get_db),
                      current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SALES_MANAGER, UserRole.FINANCE))):
    calc = RebateService(db)
    result = calc.calculate_quarterly_rebates(
        req.year, req.quarter, req.force_recalculate,
        current_user.id, current_user.username
    )
    return GenericResponse(message="返利计算完成", data=result)


@router.post("/rebate/{record_id}/unfreeze")
def unfreeze_rebate(record_id: int, reason: str = None,
                     db: Session = Depends(get_db),
                     current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.FINANCE, UserRole.REGION_DIRECTOR))):
    calc = RebateService(db)
    record = calc.unfreeze_rebate(record_id, current_user.id, current_user.username, reason)
    if not record:
        raise HTTPException(404, "返利记录不存在")
    return GenericResponse(message="返利已解冻", data={"record_code": record.record_code})


@router.post("/commission/query")
def query_commissions(req: QueryCommissionRequest,
                       db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    svc = QueryService(db)
    if current_user.role == UserRole.SALES:
        from app.models import Salesperson
        sp = db.query(Salesperson).filter(Salesperson.user_id == current_user.id).first()
        if sp:
            req.salesperson_id = sp.id
    records, total = svc.query_commissions(
        salesperson_id=req.salesperson_id,
        salesperson_code=req.salesperson_code,
        period_year=req.period_year,
        period_month=req.period_month,
        start_date=req.start_date,
        end_date=req.end_date,
        approval_status=req.approval_status,
        region=req.region,
        min_amount=req.min_amount,
        max_amount=req.max_amount,
        page=req.page,
        page_size=req.page_size
    )
    return GenericResponse(message="查询成功", data={"records": records, "total": total})


@router.post("/rebate/query")
def query_rebates(req: QueryRebateRequest,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    svc = QueryService(db)
    records, total = svc.query_rebates(
        channel_partner_id=req.channel_partner_id,
        partner_code=req.partner_code,
        period_year=req.period_year,
        period_quarter=req.period_quarter,
        status=req.status,
        region=req.region,
        is_frozen=req.is_frozen,
        min_amount=req.min_amount,
        max_amount=req.max_amount,
        page=req.page,
        page_size=req.page_size
    )
    return GenericResponse(message="查询成功", data={"records": records, "total": total})


@router.get("/commission/{record_id}")
def get_commission_detail(record_id: int,
                           db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    from app.models import CommissionRecord
    record = db.query(CommissionRecord).filter(CommissionRecord.id == record_id).first()
    if not record:
        raise HTTPException(404, "记录不存在")
    import json
    details = None
    if record.calculation_details:
        try:
            details = json.loads(record.calculation_details)
        except:
            pass
    return GenericResponse(message="成功", data={
        "id": record.id, "code": record.record_code,
        "total_commission": record.total_commission,
        "details": details
    })


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    svc = QueryService(db)
    return GenericResponse(message="成功", data=svc.get_dashboard_data())


@router.get("/commission-summary")
def commission_summary(year: int, month: int,
                        db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    calc = CommissionService(db)
    return GenericResponse(message="成功", data=calc.get_commission_summary(year, month))


@router.get("/rebate-summary")
def rebate_summary(year: int = None, quarter: int = None,
                    db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    calc = RebateService(db)
    return GenericResponse(message="成功", data=calc.get_rebate_summary(year, quarter))
