from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from io import BytesIO
from datetime import date
import os
from app.database import get_db
from app.auth import get_current_user, require_roles
from app.models import (
    User, UserRole, CommissionRecord, RebateRecord, Report,
    CommissionTierRule, BonusRule, RebateTierRule, Salesperson,
    ChannelPartner
)
from app.services.report_export import ReportExportService
from app.services.query_service import QueryService
from app.schemas import GenericResponse

router = APIRouter(prefix="/api/reports", tags=["报表与导出"])


@router.post("/generate-monthly")
def generate_monthly_report(year: int, month: int,
                             db: Session = Depends(get_db),
                             current_user: User = Depends(require_roles(
                                 UserRole.ADMIN, UserRole.FINANCE, UserRole.SALES_MANAGER
                             ))):
    svc = ReportExportService(db)
    report = svc.generate_monthly_report(year, month, current_user.id, auto=False)
    return GenericResponse(
        message="报告生成完成",
        data={
            "report_code": report.report_code,
            "title": report.title,
            "pdf_path": report.file_path_pdf,
            "excel_path": report.file_path_excel
        }
    )


@router.get("/list")
def list_reports(page: int = 1, page_size: int = 20,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    reports = db.query(Report).order_by(Report.generated_at.desc()) \
        .offset((page - 1) * page_size).limit(page_size).all()
    total = db.query(Report).count()
    data = [
        {
            "id": r.id, "code": r.report_code, "title": r.title,
            "type": r.report_type,
            "period": f"{r.period_year}-{r.period_month:02d}" if r.period_month else None,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            "is_auto": r.is_auto_generated,
            "has_pdf": bool(r.file_path_pdf),
            "has_excel": bool(r.file_path_excel)
        }
        for r in reports
    ]
    return GenericResponse(message="成功", data={"reports": data, "total": total})


@router.get("/{report_id}/download")
def download_report(report_id: int, format: str = Query("pdf", description="pdf/excel"),
                     db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(404, "报告不存在")
    path = report.file_path_pdf if format == "pdf" else report.file_path_excel
    if not path or not os.path.exists(path):
        raise HTTPException(404, f"{format.upper()} 文件不存在")
    return FileResponse(path, filename=os.path.basename(path))


@router.post("/commissions/export")
def export_commissions(salesperson_id: int = None, period_year: int = None,
                        period_month: int = None, approval_status: str = None,
                        db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    svc = QueryService(db)
    records, _ = svc.query_commissions(
        salesperson_id=salesperson_id, period_year=period_year,
        period_month=period_month, page=1, page_size=100000
    )
    if not records:
        raise HTTPException(400, "没有可导出的数据")
    record_ids = [r["id"] for r in records]
    comm_records = db.query(CommissionRecord).filter(CommissionRecord.id.in_(record_ids)).all()

    export_svc = ReportExportService(db)
    data = export_svc.export_commissions_excel(comm_records)

    filename = f"commissions_export_{date.today().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/rebates/export")
def export_rebates(channel_partner_id: int = None, period_year: int = None,
                    period_quarter: int = None, status: str = None,
                    db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    svc = QueryService(db)
    records, _ = svc.query_rebates(
        channel_partner_id=channel_partner_id, period_year=period_year,
        period_quarter=period_quarter, page=1, page_size=100000
    )
    if not records:
        raise HTTPException(400, "没有可导出的数据")
    record_ids = [r["id"] for r in records]
    rebate_records = db.query(RebateRecord).filter(RebateRecord.id.in_(record_ids)).all()

    export_svc = ReportExportService(db)
    data = export_svc.export_rebates_excel(rebate_records)

    filename = f"rebates_export_{date.today().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/rules/commission")
def get_commission_rules(db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    rules = db.query(CommissionTierRule).all()
    bonus = db.query(BonusRule).all()
    return GenericResponse(message="成功", data={
        "tier_rules": [
            {"id": r.id, "name": r.name, "category": r.product_category.value if r.product_category else None,
             "customer_level": r.customer_level.value if r.customer_level else None,
             "min": r.min_amount, "max": r.max_amount,
             "base_rate": r.base_rate, "bonus_rate": r.bonus_rate, "active": r.is_active}
            for r in rules
        ],
        "bonus_rules": [
            {"id": b.id, "name": b.name, "type": b.rule_type,
             "threshold": b.threshold_amount, "bonus": b.bonus_amount,
             "percentage": b.bonus_percentage, "active": b.is_active}
            for b in bonus
        ]
    })


@router.get("/rules/rebate")
def get_rebate_rules(db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    rules = db.query(RebateTierRule).all()
    return GenericResponse(message="成功", data={
        "rules": [
            {"id": r.id, "name": r.name, "tier": r.tier,
             "min": r.min_amount, "max": r.max_amount,
             "rate": r.rebate_rate, "bonus_rate": r.bonus_rate, "active": r.is_active}
            for r in rules
        ]
    })


@router.get("/salespersons")
def list_salespersons(db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    persons = db.query(Salesperson).all()
    return GenericResponse(message="成功", data={
        "salespersons": [
            {"id": p.id, "code": p.salesperson_code,
             "name": p.user.full_name if p.user else None,
             "tier": p.tier, "region": p.region, "quota": p.quota}
            for p in persons
        ]
    })


@router.get("/channel-partners")
def list_partners(db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    partners = db.query(ChannelPartner).all()
    return GenericResponse(message="成功", data={
        "partners": [
            {"id": p.id, "code": p.partner_code, "name": p.partner_name,
             "tier": p.tier, "region": p.region, "quarterly_budget": p.quarterly_budget}
            for p in partners
        ]
    })
