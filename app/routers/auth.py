from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import (
    authenticate_user, create_access_token, get_current_user,
    get_password_hash, require_roles
)
from app.schemas import Token, LoginRequest, UserOut
from app.models import User, UserRole
from config import settings

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value},
        expires_delta=access_token_expires
    )
    return Token(access_token=access_token)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/init-admin")
def init_admin(db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.role == UserRole.ADMIN).first()
    if existing:
        return {"message": "管理员已存在", "username": existing.username}

    admin = User(
        username="admin",
        email="admin@company.com",
        full_name="系统管理员",
        hashed_password=get_password_hash("admin123"),
        role=UserRole.ADMIN,
        department="信息技术部",
        region="总部"
    )
    db.add(admin)

    users_data = [
        ("manager1", "张明", UserRole.SALES_MANAGER, "销售部", "华东"),
        ("director1", "李华", UserRole.REGION_DIRECTOR, "华北大区", "华北"),
        ("finance1", "王芳", UserRole.FINANCE, "财务部", "总部"),
        ("auditor1", "赵强", UserRole.AUDITOR, "审计部", "总部"),
    ]
    for i, (uname, fname, role, dept, reg) in enumerate(users_data, 1):
        u = User(
            username=uname, email=f"{uname}@company.com",
            full_name=fname, hashed_password=get_password_hash("password123"),
            role=role, department=dept, region=reg,
            employee_id=f"EMP{1000 + i}", manager_id=1
        )
        db.add(u)

    for i in range(1, 31):
        sp_user = User(
            username=f"sales{i:02d}",
            email=f"sales{i:02d}@company.com",
            full_name=f"销售{i:02d}号",
            hashed_password=get_password_hash(f"sales{i:02d}"),
            role=UserRole.SALES,
            department="销售部",
            region=["华东", "华南", "华北", "西南"][i % 4],
            employee_id=f"EMP{2000 + i}",
            manager_id=2
        )
        db.add(sp_user)

    db.commit()
    return {
        "message": "初始用户创建成功",
        "admin": {"username": "admin", "password": "admin123"},
        "note": "请登录后立即修改密码"
    }
