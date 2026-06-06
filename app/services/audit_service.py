from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.models import AuditLog, LogAction
from config import settings


class AuditService:
    """审计日志服务"""

    def __init__(self, db: Session):
        self.db = db

    def log(self, user_id: Optional[int], username: Optional[str], action: LogAction,
            entity_type: str, entity_id: Optional[int] = None,
            entity_code: Optional[str] = None, field_name: Optional[str] = None,
            old_value: Optional[str] = None, new_value: Optional[str] = None,
            details: Optional[str] = None, ip_address: Optional[str] = None,
            user_agent: Optional[str] = None) -> AuditLog:
        log = AuditLog(
            timestamp=datetime.utcnow(),
            user_id=user_id,
            username=username,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_code=entity_code,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def cleanup_old_logs(self) -> int:
        """清理超过保留期的日志"""
        cutoff = datetime.utcnow() - timedelta(days=settings.LOG_RETENTION_DAYS)
        deleted = self.db.query(AuditLog).filter(AuditLog.timestamp < cutoff).delete()
        self.db.commit()
        return deleted
