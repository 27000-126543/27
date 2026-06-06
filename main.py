import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from config import settings
from app.database import engine, Base
from app.routers import auth, calculation, workflow, reports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info(f"数据库表结构已创建/检查完成")

    from app.scheduler import start_scheduler, stop_scheduler
    try:
        start_scheduler()
    except Exception as e:
        logger.warning(f"调度器启动失败: {e}")

    try:
        from sqlalchemy.orm import Session
        from app.database import SessionLocal
        from app.services.data_sync import DataSyncService
        from app.models import (
            CommissionTierRule, BonusRule, RebateTierRule,
            ProductCategory, CustomerLevel
        )
        from datetime import date

        db = SessionLocal()
        try:
            if db.query(CommissionTierRule).count() == 0:
                rules = [
                    CommissionTierRule(name="通用佣金-钻石客户", customer_level=CustomerLevel.DIAMOND,
                                       base_rate=0.035, bonus_rate=0.005, priority=100),
                    CommissionTierRule(name="通用佣金-金牌客户", customer_level=CustomerLevel.GOLD,
                                       base_rate=0.03, bonus_rate=0.003, priority=90),
                    CommissionTierRule(name="通用佣金-银牌客户", customer_level=CustomerLevel.SILVER,
                                       base_rate=0.025, priority=80),
                    CommissionTierRule(name="通用佣金-铜牌客户", customer_level=CustomerLevel.BRONZE,
                                       base_rate=0.02, priority=70),
                    CommissionTierRule(name="云服务产品高佣金", product_category=ProductCategory.CLOUD,
                                       base_rate=0.04, bonus_rate=0.008, priority=95),
                    CommissionTierRule(name="软件产品佣金", product_category=ProductCategory.SOFTWARE,
                                       base_rate=0.035, bonus_rate=0.005, priority=85),
                    CommissionTierRule(name="咨询服务佣金", product_category=ProductCategory.CONSULTING,
                                       base_rate=0.05, priority=88),
                    CommissionTierRule(name="硬件产品低佣金", product_category=ProductCategory.HARDWARE,
                                       base_rate=0.015, priority=60),
                    CommissionTierRule(name="大单阶梯奖励", min_amount=500000,
                                       base_rate=0.03, bonus_rate=0.01, priority=120),
                    CommissionTierRule(name="超大单特别奖励", min_amount=2000000,
                                       base_rate=0.035, bonus_rate=0.015, priority=150),
                ]
                db.add_all(rules)
                logger.info("已初始化佣金阶梯规则")

            if db.query(BonusRule).count() == 0:
                bonuses = [
                    BonusRule(name="月度回款超额奖", rule_type="collection_over_quota",
                              threshold_amount=1000000, bonus_percentage=0.005),
                    BonusRule(name="月度回款达标奖", rule_type="collection_over_quota",
                              threshold_amount=500000, bonus_amount=5000),
                ]
                db.add_all(bonuses)
                logger.info("已初始化奖励规则")

            if db.query(RebateTierRule).count() == 0:
                rebates = [
                    RebateTierRule(name="铂金渠道返利", tier="Platinum", min_amount=0,
                                   rebate_rate=0.05, bonus_rate=0.01, priority=100),
                    RebateTierRule(name="金牌渠道返利", tier="Gold", min_amount=0,
                                   rebate_rate=0.04, bonus_rate=0.005, priority=90),
                    RebateTierRule(name="银牌渠道返利", tier="Silver", min_amount=0,
                                   rebate_rate=0.03, priority=80),
                    RebateTierRule(name="高销量特别奖", min_amount=5000000,
                                   rebate_rate=0.04, bonus_rate=0.015, priority=120),
                    RebateTierRule(name="超高销量大奖", min_amount=10000000,
                                   rebate_rate=0.05, bonus_rate=0.02, priority=150),
                ]
                db.add_all(rebates)
                logger.info("已初始化返利阶梯规则")

            db.commit()
        finally:
            db.close()

    except Exception as e:
        logger.warning(f"初始化数据失败: {e}")

    yield

    try:
        from app.scheduler import stop_scheduler
        stop_scheduler()
    except:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="销售佣金与渠道返利自动化管理系统",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(calculation.router)
app.include_router(workflow.router)
app.include_router(reports.router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def read_root():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "message": "销售佣金与渠道返利自动化管理系统 API"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": __import__("datetime").datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
