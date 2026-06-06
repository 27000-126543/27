import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, date
from contextlib import contextmanager
from app.database import SessionLocal
from app.services.data_sync import DataSyncService
from app.services.commission_calculator import CommissionService
from app.services.rebate_calculator import RebateService
from app.services.report_export import ReportExportService
from app.services.audit_service import AuditService
from app.models import LogAction
from config import settings

logger = logging.getLogger(__name__)


@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def job_data_sync():
    """定时任务：每日同步CRM和订单数据"""
    logger.info("开始执行数据同步定时任务")
    try:
        with get_db_context() as db:
            sync = DataSyncService(db)
            crm_result = sync.sync_from_crm()
            logger.info(f"CRM同步完成: {crm_result}")
            order_result = sync.sync_from_order_system()
            logger.info(f"订单同步完成: {order_result}")
    except Exception as e:
        logger.error(f"数据同步任务失败: {e}", exc_info=True)


def job_monthly_commission_calculation():
    """定时任务：每月1号计算上月佣金"""
    logger.info("开始执行月度佣金计算任务")
    try:
        with get_db_context() as db:
            today = date.today()
            if today.month == 1:
                prev_year = today.year - 1
                prev_month = 12
            else:
                prev_year = today.year
                prev_month = today.month - 1

            calc = CommissionService(db)
            result = calc.calculate_monthly_commission(
                prev_year, prev_month, force_recalculate=False,
                user_id=None, username="scheduler"
            )
            logger.info(f"月度佣金计算完成: {result}")
    except Exception as e:
        logger.error(f"月度佣金计算任务失败: {e}", exc_info=True)


def job_quarterly_rebate_calculation():
    """定时任务：每季度首月计算上季度返利"""
    logger.info("开始执行季度返利计算任务")
    try:
        with get_db_context() as db:
            today = date.today()
            q = ((today.month - 1) // 3) + 1
            if q == 1:
                prev_year = today.year - 1
                prev_q = 4
            else:
                prev_year = today.year
                prev_q = q - 1

            if today.month in [1, 4, 7, 10]:
                calc = RebateService(db)
                result = calc.calculate_quarterly_rebates(
                    prev_year, prev_q, force_recalculate=False,
                    user_id=None, username="scheduler"
                )
                logger.info(f"季度返利计算完成: {result}")
    except Exception as e:
        logger.error(f"季度返利计算任务失败: {e}", exc_info=True)


def job_monthly_report_generation():
    """定时任务：每月5号生成月度分析报告"""
    logger.info("开始执行月度报告生成任务")
    try:
        with get_db_context() as db:
            today = date.today()
            if today.day == settings.REPORT_GENERATION_DAY:
                if today.month == 1:
                    prev_year = today.year - 1
                    prev_month = 12
                else:
                    prev_year = today.year
                    prev_month = today.month - 1

                report_svc = ReportExportService(db)
                report = report_svc.generate_monthly_report(
                    prev_year, prev_month, user_id=None, auto=True
                )
                logger.info(f"月度报告生成完成: {report.report_code}, PDF: {report.file_path_pdf}")
    except Exception as e:
        logger.error(f"月度报告生成任务失败: {e}", exc_info=True)


def job_log_cleanup():
    """定时任务：每周清理过期日志"""
    logger.info("开始执行日志清理任务")
    try:
        with get_db_context() as db:
            audit = AuditService(db)
            deleted = audit.cleanup_old_logs()
            logger.info(f"日志清理完成，删除 {deleted} 条旧记录")
    except Exception as e:
        logger.error(f"日志清理任务失败: {e}", exc_info=True)


scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def start_scheduler():
    """启动所有定时任务"""
    scheduler.add_job(
        job_data_sync,
        CronTrigger(hour=settings.DATA_SYNC_HOUR, minute=settings.DATA_SYNC_MINUTE),
        id="daily_data_sync",
        name="每日数据同步",
        replace_existing=True
    )

    scheduler.add_job(
        job_monthly_commission_calculation,
        CronTrigger(day=1, hour=3, minute=0),
        id="monthly_commission",
        name="月度佣金计算",
        replace_existing=True
    )

    scheduler.add_job(
        job_quarterly_rebate_calculation,
        CronTrigger(day=1, hour=4, minute=0),
        id="quarterly_rebate",
        name="季度返利计算",
        replace_existing=True
    )

    scheduler.add_job(
        job_monthly_report_generation,
        CronTrigger(day=settings.REPORT_GENERATION_DAY,
                    hour=settings.REPORT_GENERATION_TIME.hour,
                    minute=settings.REPORT_GENERATION_TIME.minute),
        id="monthly_report",
        name="月度报告生成",
        replace_existing=True
    )

    scheduler.add_job(
        job_log_cleanup,
        CronTrigger(day_of_week="sun", hour=5, minute=0),
        id="weekly_log_cleanup",
        name="每周日志清理",
        replace_existing=True
    )

    scheduler.start()
    logger.info("定时任务调度器已启动")
    for job in scheduler.get_jobs():
        logger.info(f"已注册任务: {job.name} (ID: {job.id}, 触发器: {job.trigger})")


def stop_scheduler():
    """停止调度器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("定时任务调度器已停止")
