from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from app.database import get_db
from app.auth import get_current_user, require_roles
from app.models import User, UserRole
from app.services.approval_workflow import ApprovalService
from app.services.appeal_service import AppealService
from app.services.query_service import QueryService
from app.schemas import ApprovalRequest, AppealSubmitRequest, AppealReviewRequest, GenericResponse

router = APIRouter(prefix="/api/workflow", tags=["审批与申诉"])


@router.get("/pending")
def get_pending_approvals(db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    svc = ApprovalService(db)
    return GenericResponse(message="成功", data=svc.get_pending_approvals(current_user.id, current_user.role))


@router.post("/commission/{record_id}/approve")
def approve_commission(record_id: int, req: ApprovalRequest,
                        db: Session = Depends(get_db),
                        current_user: User = Depends(require_roles(
                            UserRole.SALES_MANAGER, UserRole.REGION_DIRECTOR,
                            UserRole.FINANCE, UserRole.ADMIN
                        ))):
    svc = ApprovalService(db)
    record = svc.approve_commission(record_id, current_user.id, current_user.full_name, req.comments)
    if not record:
        raise HTTPException(404, "佣金记录不存在")
    return GenericResponse(message="审批通过", data={"record_code": record.record_code, "status": record.approval_status.value})


@router.post("/commission/{record_id}/reject")
def reject_commission(record_id: int, req: ApprovalRequest,
                       db: Session = Depends(get_db),
                       current_user: User = Depends(require_roles(
                           UserRole.SALES_MANAGER, UserRole.REGION_DIRECTOR,
                           UserRole.FINANCE, UserRole.ADMIN
                       ))):
    svc = ApprovalService(db)
    record = svc.reject_commission(record_id, current_user.id, current_user.full_name, req.comments)
    if not record:
        raise HTTPException(404, "佣金记录不存在")
    return GenericResponse(message="已驳回", data={"record_code": record.record_code})


@router.post("/commission/{record_id}/submit")
def submit_commission_approval(record_id: int,
                                db: Session = Depends(get_db),
                                current_user: User = Depends(require_roles(
                                    UserRole.SALES_MANAGER, UserRole.ADMIN, UserRole.FINANCE
                                ))):
    svc = ApprovalService(db)
    record = svc.trigger_commission_approval(record_id, current_user.id, current_user.full_name)
    if not record:
        raise HTTPException(404, "佣金记录不存在")
    return GenericResponse(message="已提交审批", data={"record_code": record.record_code, "level": record.approval_level})


@router.post("/rebate/{record_id}/approve")
def approve_rebate(record_id: int, req: ApprovalRequest,
                    db: Session = Depends(get_db),
                    current_user: User = Depends(require_roles(
                        UserRole.FINANCE, UserRole.ADMIN, UserRole.REGION_DIRECTOR
                    ))):
    svc = ApprovalService(db)
    record = svc.approve_rebate(record_id, current_user.id, current_user.full_name, req.comments)
    if not record:
        raise HTTPException(404, "返利记录不存在")
    return GenericResponse(message="审批通过", data={"record_code": record.record_code, "status": record.approval_status.value})


@router.post("/rebate/{record_id}/reject")
def reject_rebate(record_id: int, req: ApprovalRequest,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(require_roles(
                       UserRole.FINANCE, UserRole.ADMIN, UserRole.REGION_DIRECTOR
                   ))):
    svc = ApprovalService(db)
    record = svc.reject_rebate(record_id, current_user.id, current_user.full_name, req.comments)
    if not record:
        raise HTTPException(404, "返利记录不存在")
    return GenericResponse(message="已驳回", data={"record_code": record.record_code})


@router.post("/appeals")
def submit_appeal(req: AppealSubmitRequest,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    svc = AppealService(db)
    appeal = svc.submit_appeal(
        current_user.id, current_user.full_name,
        req.appeal_type, req.reason,
        req.commission_record_id, req.rebate_record_id, req.evidence
    )
    return GenericResponse(message="申诉已提交", data={"appeal_code": appeal.appeal_code})


@router.get("/appeals/mine")
def get_my_appeals(db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    svc = AppealService(db)
    return GenericResponse(message="成功", data={"appeals": svc.get_user_appeals(current_user.id)})


@router.get("/appeals/pending")
def get_pending_reviews(db: Session = Depends(get_db),
                         current_user: User = Depends(require_roles(
                             UserRole.ADMIN, UserRole.SALES_MANAGER,
                             UserRole.REGION_DIRECTOR, UserRole.AUDITOR, UserRole.FINANCE
                         ))):
    svc = AppealService(db)
    return GenericResponse(message="成功", data={"appeals": svc.get_pending_reviews()})


@router.get("/appeals/{appeal_id}")
def get_appeal_detail(appeal_id: int,
                       db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    svc = AppealService(db)
    data = svc.get_appeal_related_data(appeal_id)
    if not data:
        raise HTTPException(404, "申诉不存在")
    return GenericResponse(message="成功", data=data)


@router.post("/appeals/{appeal_id}/review")
def review_appeal(appeal_id: int, req: AppealReviewRequest,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(require_roles(
                       UserRole.ADMIN, UserRole.SALES_MANAGER,
                       UserRole.REGION_DIRECTOR, UserRole.AUDITOR, UserRole.FINANCE
                   ))):
    svc = AppealService(db)
    appeal = svc.review_appeal(
        appeal_id, current_user.id, current_user.full_name,
        req.approved, req.review_comments
    )
    if not appeal:
        raise HTTPException(404, "申诉不存在")
    return GenericResponse(
        message="复核完成",
        data={"appeal_code": appeal.appeal_code, "status": appeal.status.value, "resolution": appeal.resolution_notes}
    )


@router.get("/approval-history")
def get_approval_history(target_type: str = None, target_id: int = None,
                          start_date: date = None, end_date: date = None,
                          page: int = 1, page_size: int = 50,
                          db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    svc = QueryService(db)
    records, total = svc.query_approval_history(
        target_type=target_type, target_id=target_id,
        start_date=start_date, end_date=end_date,
        page=page, page_size=page_size
    )
    return GenericResponse(message="成功", data={"records": records, "total": total})
