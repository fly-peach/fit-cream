# FitCream 后端架构设计

> FastAPI 待办业务 + LangGraph Agent 融合为单一服务

---

## 目录

1. [整体架构](#一整体架构)
2. [目录结构](#二目录结构)
3. [核心模块职责](#三核心模块职责)
4. [数据库设计](#四数据库设计)
5. [API 端点规格](#五api-端点规格)
6. [Agent 与业务融合设计](#六agent-与待办业务融合设计)
7. [Agent Tools 规格](#七agent-tools-规格)
8. [System Prompt 设计](#八system-prompt-设计)
9. [SSE 流式输出设计](#九sse-流式输出设计)
10. [认证与安全](#十认证与安全)
11. [错误码规范](#十一错误码规范)
12. [环境变量配置](#十二环境变量配置)
13. [日志与监控](#十三日志与监控)
14. [测试策略](#十四测试策略)
15. [性能优化](#十五性能优化)
16. [部署架构](#十六部署架构)
17. [开发指南](#十七开发指南)
18. [关键依赖](#十八关键依赖)
19. [开发里程碑](#十九开发里程碑m1-m3)

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│   REST API（CRUD）          │        SSE（Agent 对话）           │
└─────────────┬───────────────┼────────────────┬──────────────────┘
              │               │                │
              ▼               ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Application                         │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    API Layer (routers/)                  │   │
│  │  auth │ users │ plans │ checkins │ stats │ agent(SSE)   │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           │                                     │
│  ┌────────────────────────▼────────────────────────────────┐   │
│  │                 Service Layer (services/)                │   │
│  │  AuthService │ PlanService │ CheckinService │ StatsSvc  │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           │                                     │
│  ┌────────────────────────▼────────────────────────────────┐   │
│  │              LangGraph Agent (agents/)                   │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │  create_react_agent                               │  │   │
│  │  │  Tools → 直接调用 Service Layer（同进程）          │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│  ┌────────────────────────▼────────────────────────────────┐   │
│  │                Data Layer (models/ + database.py)        │   │
│  │  SQLAlchemy 2.0 Async ORM                               │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PostgreSQL 16                              │
│  业务表（users, plans, checkins...）+ checkpoints（对话状态）    │
└─────────────────────────────────────────────────────────────────┘
```

### 核心设计原则

| 原则 | 说明 |
|------|------|
| **同进程融合** | Agent 和待办业务共享同一个 FastAPI 进程、同一个 Service 层、同一个数据库连接 |
| **Service 复用** | Agent 的 Tools 直接调用 Service 函数，不走 HTTP，保证数据一致性 |
| **异步优先** | 全链路 async/await，使用 asyncpg 异步驱动 |
| **类型安全** | Pydantic v2 校验请求/响应，SQLAlchemy 2.0 类型注解 |
| **关注点分离** | Router（路由）→ Service（业务）→ Model（数据）三层架构 |

---

## 二、目录结构

```
rogers/
├── app/                           ← FastAPI 应用主体
│   ├── __init__.py
│   ├── main.py                    ← FastAPI app 入口 + 生命周期
│   ├── config.py                  ← pydantic-settings 配置
│   ├── database.py                ← async engine / session / Base
│   ├── dependencies.py            ← 公共依赖（get_db, get_current_user）
│   │
│   ├── models/                    ← SQLAlchemy ORM Models
│   │   ├── __init__.py            ← 导出所有 model（Alembic 需要）
│   │   ├── user.py                ← User
│   │   ├── plan.py                ← Plan, PlanDay, PlanDayExercise
│   │   ├── checkin.py             ← Checkin, CheckinExercise
│   │   ├── exercise.py            ← Exercise（动作库）
│   │   ├── conversation.py        ← Conversation（对话历史）
│   │   └── achievement.py         ← Achievement
│   │
│   ├── schemas/                   ← Pydantic v2 Schemas（请求/响应）
│   │   ├── __init__.py
│   │   ├── common.py              ← 统一响应 ResponseModel, 分页
│   │   ├── auth.py                ← RegisterRequest, LoginResponse, TokenPair
│   │   ├── user.py                ← UserOut, UserUpdate
│   │   ├── plan.py                ← PlanCreate, PlanOut, PlanDayCreate
│   │   ├── checkin.py             ← CheckinCreate, CheckinOut
│   │   ├── stats.py               ← WeeklyStats, MonthlyTrend, BodyTrend
│   │   └── agent.py               ← ChatRequest, ChatEvent
│   │
│   ├── routers/                   ← API 路由
│   │   ├── __init__.py            ← 汇总 router
│   │   ├── auth.py                ← /api/auth/*
│   │   ├── users.py               ← /api/users/*
│   │   ├── plans.py               ← /api/plans/*
│   │   ├── checkins.py            ← /api/checkins/*
│   │   ├── stats.py               ← /api/stats/*
│   │   └── agent.py               ← /api/agent/*（SSE 流式）
│   │
│   ├── services/                  ← 业务逻辑层（Agent Tools 也调这里）
│   │   ├── __init__.py
│   │   ├── auth_service.py        ← 注册/登录/刷新/密码哈希
│   │   ├── user_service.py        ← 用户 CRUD
│   │   ├── plan_service.py        ← 计划 CRUD + 智能生成逻辑
│   │   ├── checkin_service.py     ← 打卡 + streak 计算
│   │   ├── stats_service.py       ← 聚合统计查询
│   │   ├── exercise_service.py    ← 动作库查询
│   │   └── achievement_service.py ← 成就解锁检测
│   │
│   └── utils/
│       ├── __init__.py
│       ├── security.py            ← JWT 生成/验证, bcrypt
│       ├── response.py            ← 统一响应包装
│       ├── exceptions.py          ← 自定义异常 + 全局 handler
│       └── logger.py              ← 日志配置
│
├── agents/                        ← LangGraph Agent
│   ├── __init__.py
│   ├── agent_graph.py             ← create_react_agent 构建 + 导出 graph
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── agent_factory.py       ← Agent 工厂（创建/配置 agent）
│   │   └── model_factory.py       ← LLM 模型工厂
│   └── harness/
│       ├── __init__.py
│       ├── middleware/            ← Agent 中间件（日志、限流）
│       │   ├── __init__.py
│       │   └── logging_middleware.py
│       ├── prompts/               ← System prompts
│       │   ├── __init__.py
│       │   └── system.py          ← SYSTEM_PROMPT
│       └── tools/                 ← LangChain Tools
│           ├── __init__.py        ← 导出所有 tools
│           ├── plan_tools.py      ← create_plan_tool, adjust_plan_tool
│           ├── checkin_tools.py   ← checkin_tool
│           ├── stats_tools.py     ← query_stats_tool
│           ├── exercise_tools.py  ← get_exercises_tool
│           └── user_tools.py      ← get_user_profile_tool
│
├── alembic/                       ← 数据库迁移
│   ├── env.py
│   ├── script.py.mako
│   ├── versions/
│   └── alembic.ini
│
├── seeds/
│   ├── exercises.json             ← 100+ 动作种子数据
│   └── seed.py                    ← 灌入脚本
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                ← fixtures（test client, test db）
│   ├── test_auth.py
│   ├── test_plans.py
│   ├── test_checkins.py
│   ├── test_stats.py
│   └── test_agent.py
│
├── langgraph.json                 ← langgraph dev 配置
├── pyproject.toml                 ← uv 项目配置
├── uv.lock
├── .env.example
└── Dockerfile
```

---

## 三、核心模块职责

### 3.1 入口 `main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, init_db
from app.routers import api_router
from app.utils.exceptions import register_exception_handlers
from agents.agent_graph import init_agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()           # 初始化数据库连接池
    await init_agent()        # 初始化 Agent + checkpointer
    yield
    # Shutdown
    await engine.dispose()    # 关闭数据库连接

app = FastAPI(
    title="FitCream API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix="/api")

# 注册异常处理器
register_exception_handlers(app)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
```

| 职责 | 说明 |
|------|------|
| 创建 FastAPI app | 配置 CORS、异常处理器、中间件 |
| 注册路由 | 挂载所有 routers |
| 生命周期管理 | startup: 初始化 DB 连接池 + Agent checkpointer；shutdown: 关闭连接 |
| 健康检查 | `GET /health` |

### 3.2 配置 `config.py`

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "FitCream"
    DEBUG: bool = False
    API_PREFIX: str = "/api"
    
    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://fitcream:fitcream@localhost:5432/fitcream"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    
    # JWT
    JWT_SECRET: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # LLM / Agent
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    AGENT_MODEL: str = "gpt-4o-mini"
    AGENT_TEMPERATURE: float = 0.7
    AGENT_MAX_TOKENS: int = 2000
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Rate Limit
    AGENT_RATE_LIMIT: int = 10  # requests per minute
    
    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or text
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

### 3.3 数据库 `database.py`

```python
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator

from app.config import settings

# 异步引擎
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,  # 连接健康检查
    echo=settings.DEBUG,
)

# Session 工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# 声明式基类
class Base(DeclarativeBase):
    pass

# 依赖注入：获取 db session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# 初始化数据库（创建表）
async def init_db():
    async with engine.begin() as conn:
        # 生产环境使用 Alembic，开发环境可自动创建
        if settings.DEBUG:
            from app.models import *  # noqa: 导入所有 model
            await conn.run_sync(Base.metadata.create_all)
```

| 组件 | 说明 |
|------|------|
| `engine` | `create_async_engine(DATABASE_URL)` 异步引擎 |
| `async_session_factory` | `async_sessionmaker` Session 工厂 |
| `Base` | `DeclarativeBase` 所有 model 继承 |
| `get_db` | 依赖注入，yield session，自动 commit/rollback |

### 3.4 Service 层

**关键设计**：Service 函数接收 `db: AsyncSession` 参数，既可被 Router 调用，也可被 Agent Tools 调用。

| Service | 核心方法 | 说明 |
|---------|----------|------|
| `AuthService` | `register`, `login`, `refresh_token`, `verify_password`, `hash_password` | 认证相关 |
| `UserService` | `get_by_id`, `get_by_email`, `update_profile` | 用户管理 |
| `PlanService` | `create_plan`, `list_plans`, `get_plan_detail`, `update_plan`, `delete_plan`, `add_plan_day`, `generate_plan_from_goal` | 计划管理 + 智能生成 |
| `CheckinService` | `create_checkin`, `list_checkins`, `get_streak`, `update_checkin`, `get_by_date` | 打卡 + 连续天数 |
| `StatsService` | `get_weekly_stats`, `get_monthly_trend`, `get_body_trend` | 聚合统计 |
| `ExerciseService` | `list_by_muscle_group`, `search`, `get_all`, `get_by_id` | 动作库查询 |
| `AchievementService` | `check_and_unlock`, `list_user_achievements`, `get_achievement_definitions` | 成就系统 |

**Service 示例代码**：

```python
# app/services/plan_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime

from app.models.plan import Plan, PlanDay, PlanDayExercise
from app.models.exercise import Exercise
from app.schemas.plan import PlanCreate, PlanUpdate, PlanDayCreate
from app.utils.exceptions import NotFoundException, ForbiddenException

class PlanService:
    @staticmethod
    async def create_plan(
        db: AsyncSession,
        user_id: UUID,
        data: PlanCreate,
    ) -> Plan:
        """创建训练计划"""
        plan = Plan(
            user_id=user_id,
            name=data.name,
            goal=data.goal,
            difficulty=data.difficulty,
            weeks=data.weeks,
            status="active",
        )
        db.add(plan)
        await db.flush()
        
        # 如果包含训练日，一并创建
        if data.days:
            for day_data in data.days:
                await PlanService._create_plan_day(db, plan.id, day_data)
        
        await db.refresh(plan)
        return plan
    
    @staticmethod
    async def get_plan_detail(
        db: AsyncSession,
        plan_id: UUID,
        user_id: UUID,
    ) -> Plan:
        """获取计划详情（含训练日和动作）"""
        result = await db.execute(
            select(Plan).where(Plan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        
        if not plan:
            raise NotFoundException("计划不存在")
        if plan.user_id != user_id:
            raise ForbiddenException("无权访问此计划")
        
        return plan
    
    @staticmethod
    async def generate_plan_from_goal(
        db: AsyncSession,
        user_id: UUID,
        goal: str,
        days_per_week: int,
        difficulty: str = "beginner",
    ) -> Plan:
        """根据目标智能生成计划（Agent 调用）"""
        # 1. 获取用户身体数据
        # 2. 根据目标选择训练模板
        # 3. 根据体能调整强度
        # 4. 创建计划 + 训练日 + 动作
        ...
```

### 3.5 Router 层

| Router | 端点前缀 | 特殊说明 |
|--------|----------|----------|
| `auth` | `/api/auth` | 无需认证 |
| `users` | `/api/users` | 需 Bearer token |
| `plans` | `/api/plans` | 需认证，校验归属 |
| `checkins` | `/api/checkins` | 需认证，日期校验 |
| `stats` | `/api/stats` | 需认证 |
| `agent` | `/api/agent` | 需认证，Rate limit 10/min |

**Router 示例代码**：

```python
# app/routers/plans.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import ResponseModel, PaginatedResponse
from app.schemas.plan import PlanCreate, PlanOut, PlanUpdate
from app.services.plan_service import PlanService

router = APIRouter(prefix="/plans", tags=["plans"])

@router.post("", response_model=ResponseModel[PlanOut])
async def create_plan(
    data: PlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建训练计划"""
    plan = await PlanService.create_plan(db, current_user.id, data)
    return ResponseModel(data=PlanOut.model_validate(plan))

@router.get("", response_model=ResponseModel[PaginatedResponse[PlanOut]])
async def list_plans(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, pattern="^(active|archived|completed)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取计划列表"""
    plans, total = await PlanService.list_plans(
        db, current_user.id, page, size, status
    )
    return ResponseModel(data=PaginatedResponse(
        items=[PlanOut.model_validate(p) for p in plans],
        total=total,
        page=page,
        size=size,
    ))

@router.get("/{plan_id}", response_model=ResponseModel[PlanOut])
async def get_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取计划详情"""
    plan = await PlanService.get_plan_detail(db, plan_id, current_user.id)
    return ResponseModel(data=PlanOut.model_validate(plan))
```

### 3.6 依赖注入 `dependencies.py`

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.utils.security import verify_access_token
from app.utils.exceptions import UnauthorizedException

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT token 解析当前用户"""
    token = credentials.credentials
    payload = verify_access_token(token)
    
    if not payload:
        raise UnauthorizedException("无效的访问令牌")
    
    user_id = UUID(payload.get("sub"))
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise UnauthorizedException("用户不存在")
    
    return user
```

---

## 四、数据库设计

### 4.1 ER 关系图

```
┌─────────────┐       ┌─────────────┐       ┌─────────────────────┐
│    users    │──1:N──│    plans    │──1:N──│     plan_days       │
└─────────────┘       └─────────────┘       └──────────┬──────────┘
       │                                               │
       │1:N                                         1:N│
       ▼                                               ▼
┌─────────────┐                              ┌─────────────────────┐
│  checkins   │                              │ plan_day_exercises  │
└──────┬──────┘                              └──────────┬──────────┘
       │                                              │
       │1:N                                        N:1│
       ▼                                              ▼
┌─────────────────────┐                    ┌─────────────────────┐
│ checkin_exercises   │──N:1──────────────│     exercises       │
└─────────────────────┘                    └─────────────────────┘

┌─────────────┐       ┌─────────────────┐
│    users    │──1:N──│  conversations  │
└─────────────┘       └─────────────────┘
       │
       │1:N
       ▼
┌─────────────────┐
│  achievements   │
└─────────────────┘
```

### 4.2 SQLAlchemy Models

#### User Model

```python
# app/models/user.py
from sqlalchemy import String, Integer, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from datetime import datetime
from typing import Optional, List

from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100))
    
    # 身体数据
    height_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    age: Mapped[Optional[int]] = mapped_column(Integer)
    gender: Mapped[Optional[str]] = mapped_column(String(10))  # male/female/other
    
    # 健身目标
    goal: Mapped[Optional[str]] = mapped_column(String(50))
    # lose_fat / gain_muscle / maintain / improve_health
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # 关系
    plans: Mapped[List["Plan"]] = relationship(back_populates="user", lazy="selectin")
    checkins: Mapped[List["Checkin"]] = relationship(back_populates="user", lazy="selectin")
    achievements: Mapped[List["Achievement"]] = relationship(back_populates="user")
```

#### Plan Models

```python
# app/models/plan.py
from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4, UUID as PyUUID
from datetime import datetime
from typing import Optional, List

from app.database import Base

class Plan(Base):
    __tablename__ = "plans"
    
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    goal: Mapped[Optional[str]] = mapped_column(String(50))
    difficulty: Mapped[Optional[str]] = mapped_column(String(20))  # beginner/intermediate/advanced
    weeks: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/archived/completed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # 关系
    user: Mapped["User"] = relationship(back_populates="plans")
    days: Mapped[List["PlanDay"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )

class PlanDay(Base):
    __tablename__ = "plan_days"
    
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    plan_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), index=True
    )
    day_of_week: Mapped[int] = mapped_column(Integer)  # 1=周一 ... 7=周日
    focus: Mapped[Optional[str]] = mapped_column(String(100))  # 训练重点
    rest_seconds: Mapped[int] = mapped_column(Integer, default=60)
    
    # 关系
    plan: Mapped["Plan"] = relationship(back_populates="days")
    exercises: Mapped[List["PlanDayExercise"]] = relationship(
        back_populates="plan_day", cascade="all, delete-orphan", lazy="selectin"
    )

class PlanDayExercise(Base):
    __tablename__ = "plan_day_exercises"
    
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    plan_day_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_days.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercises.id"), index=True
    )
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    
    # 关系
    plan_day: Mapped["PlanDay"] = relationship(back_populates="exercises")
    exercise: Mapped["Exercise"] = relationship(lazy="selectin")
```

#### Checkin Models

```python
# app/models/checkin.py
from sqlalchemy import String, Integer, Numeric, Date, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4, UUID as PyUUID
from datetime import datetime, date
from typing import Optional, List

from app.database import Base

class Checkin(Base):
    __tablename__ = "checkins"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_checkin_user_date"),
    )
    
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    plan_day_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_days.id", ondelete="SET NULL")
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    mood: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user: Mapped["User"] = relationship(back_populates="checkins")
    exercises: Mapped[List["CheckinExercise"]] = relationship(
        back_populates="checkin", cascade="all, delete-orphan", lazy="selectin"
    )

class CheckinExercise(Base):
    __tablename__ = "checkin_exercises"
    
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    checkin_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checkins.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exercises.id"), index=True
    )
    sets_done: Mapped[Optional[int]] = mapped_column(Integer)
    reps_done: Mapped[Optional[int]] = mapped_column(Integer)
    weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    
    # 关系
    checkin: Mapped["Checkin"] = relationship(back_populates="exercises")
    exercise: Mapped["Exercise"] = relationship(lazy="selectin")
```

#### Exercise Model

```python
# app/models/exercise.py
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4, UUID as PyUUID
from typing import Optional

from app.database import Base

class Exercise(Base):
    __tablename__ = "exercises"
    
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    muscle_group: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    # chest / back / legs / shoulders / arms / core / full_body
    equipment: Mapped[Optional[str]] = mapped_column(String(100))
    # barbell / dumbbell / machine / bodyweight / cable / kettlebell
    description: Mapped[Optional[str]] = mapped_column(Text)
    difficulty: Mapped[Optional[str]] = mapped_column(String(20))  # beginner/intermediate/advanced
```

#### Conversation Model

```python
# app/models/conversation.py
from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from uuid import uuid4, UUID as PyUUID
from datetime import datetime
from typing import Optional

from app.database import Base

class Conversation(Base):
    __tablename__ = "conversations"
    
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    thread_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user / assistant / tool
    content: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
```

#### Achievement Model

```python
# app/models/achievement.py
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4, UUID as PyUUID
from datetime import datetime
from typing import Optional

from app.database import Base

class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "type", name="uq_achievement_user_type"),
    )
    
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(50))
    # streak_7 / streak_30 / streak_100 / first_plan / total_50_workouts / total_100_workouts
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user: Mapped["User"] = relationship(back_populates="achievements")
```

### 4.3 索引设计

```sql
-- 高频查询索引
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_plans_user_status ON plans(user_id, status);
CREATE INDEX idx_plan_days_plan ON plan_days(plan_id);
CREATE INDEX idx_checkins_user_date ON checkins(user_id, date DESC);
CREATE INDEX idx_checkin_exercises_checkin ON checkin_exercises(checkin_id);
CREATE INDEX idx_conversations_user_created ON conversations(user_id, created_at DESC);
CREATE INDEX idx_exercises_muscle ON exercises(muscle_group);
CREATE INDEX idx_achievements_user ON achievements(user_id);
```

### 4.4 种子数据格式

```json
// seeds/exercises.json
[
  {
    "name": "杠铃卧推",
    "name_en": "Barbell Bench Press",
    "muscle_group": "chest",
    "equipment": "barbell",
    "difficulty": "intermediate",
    "description": "经典胸部训练动作，主要锻炼胸大肌中部"
  },
  {
    "name": "上斜哑铃卧推",
    "name_en": "Incline Dumbbell Press",
    "muscle_group": "chest",
    "equipment": "dumbbell",
    "difficulty": "intermediate",
    "description": "锻炼胸大肌上部"
  },
  {
    "name": "深蹲",
    "name_en": "Barbell Squat",
    "muscle_group": "legs",
    "equipment": "barbell",
    "difficulty": "intermediate",
    "description": "下肢训练之王，锻炼股四头肌、臀大肌"
  }
  // ... 100+ 动作
]
```

---

## 五、API 端点规格

### 5.1 统一响应格式

```python
# app/schemas/common.py
from pydantic import BaseModel
from typing import TypeVar, Generic, Optional, List
from math import ceil

T = TypeVar("T")

class ResponseModel(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: Optional[T] = None

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    
    @property
    def total_pages(self) -> int:
        return ceil(self.total / self.size) if self.size > 0 else 0
    
    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages
```

### 5.2 认证模块

#### POST /api/auth/register

**请求体**：
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "name": "张三"
}
```

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "user@example.com",
      "name": "张三",
      "created_at": "2024-01-15T10:30:00Z"
    },
    "tokens": {
      "access_token": "eyJhbGciOiJIUzI1NiIs...",
      "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
      "token_type": "bearer",
      "expires_in": 900
    }
  }
}
```

**错误响应**：
```json
{
  "code": 40001,
  "message": "邮箱已注册",
  "data": null
}
```

#### POST /api/auth/login

**请求体**：
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**响应**：同注册响应

#### POST /api/auth/refresh

**请求体**：
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

### 5.3 用户模块

#### GET /api/users/me

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "name": "张三",
    "height_cm": 175.5,
    "weight_kg": 70.0,
    "age": 28,
    "gender": "male",
    "goal": "gain_muscle",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

#### PUT /api/users/me

**请求体**（部分更新）：
```json
{
  "weight_kg": 68.5,
  "goal": "lose_fat"
}
```

### 5.4 训练计划模块

#### POST /api/plans

**请求体**：
```json
{
  "name": "增肌计划 - 第一阶段",
  "goal": "gain_muscle",
  "difficulty": "intermediate",
  "weeks": 8,
  "days": [
    {
      "day_of_week": 1,
      "focus": "胸部 + 三头",
      "exercises": [
        {
          "exercise_id": "550e8400-e29b-41d4-a716-446655440001",
          "sets": 4,
          "reps": 10,
          "weight_kg": 60.0
        }
      ]
    }
  ]
}
```

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "增肌计划 - 第一阶段",
    "goal": "gain_muscle",
    "difficulty": "intermediate",
    "weeks": 8,
    "status": "active",
    "days": [...],
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

#### GET /api/plans

**查询参数**：
- `page`: 页码（默认 1）
- `size`: 每页数量（默认 20，最大 100）
- `status`: 筛选状态（active / archived / completed）

#### GET /api/plans/{id}

**响应**：包含完整训练日和动作详情

#### PUT /api/plans/{id}

**请求体**（部分更新）：
```json
{
  "name": "更新后的计划名称",
  "status": "archived"
}
```

#### DELETE /api/plans/{id}

软删除，将 status 设为 `archived`

#### POST /api/plans/{id}/days

**请求体**：
```json
{
  "day_of_week": 3,
  "focus": "背部 + 二头",
  "rest_seconds": 90,
  "exercises": [
    {
      "exercise_id": "...",
      "sets": 4,
      "reps": 8,
      "weight_kg": 80.0
    }
  ]
}
```

### 5.5 打卡模块

#### POST /api/checkins

**请求体**：
```json
{
  "date": "2024-01-15",
  "plan_day_id": "550e8400-e29b-41d4-a716-446655440001",
  "duration_min": 60,
  "mood": 4,
  "note": "今天状态不错，深蹲 PR 了",
  "exercises": [
    {
      "exercise_id": "...",
      "sets_done": 5,
      "reps_done": 5,
      "weight_kg": 100.0
    }
  ]
}
```

**校验规则**：
- `date` 不能是未来日期
- `mood` 范围 1-5
- `duration_min` 必须 > 0
- 同一天只能打卡一次

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "...",
    "date": "2024-01-15",
    "duration_min": 60,
    "mood": 4,
    "streak": 7,
    "exercises": [...],
    "created_at": "2024-01-15T18:30:00Z"
  }
}
```

#### GET /api/checkins

**查询参数**：
- `start`: 开始日期（YYYY-MM-DD）
- `end`: 结束日期（YYYY-MM-DD）
- `page`, `size`: 分页

#### GET /api/checkins/streak

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "current_streak": 7,
    "longest_streak": 21,
    "last_checkin_date": "2024-01-15"
  }
}
```

#### PUT /api/checkins/{id}

补卡/修改，请求体同创建

### 5.6 统计模块

#### GET /api/stats/weekly

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "week_start": "2024-01-15",
    "week_end": "2024-01-21",
    "total_workouts": 4,
    "total_duration_min": 240,
    "total_sets": 64,
    "completion_rate": 0.8,
    "planned_workouts": 5,
    "daily_breakdown": [
      {"date": "2024-01-15", "completed": true, "duration_min": 60},
      {"date": "2024-01-16", "completed": true, "duration_min": 55}
    ]
  }
}
```

#### GET /api/stats/monthly

**查询参数**：
- `year`: 年份（默认当前年）
- `month`: 月份（默认当前月）

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "year": 2024,
    "month": 1,
    "total_workouts": 18,
    "total_duration_min": 1080,
    "average_mood": 3.8,
    "weekly_trend": [
      {"week": 1, "workouts": 4, "duration_min": 240},
      {"week": 2, "workouts": 5, "duration_min": 300}
    ]
  }
}
```

#### GET /api/stats/body

**查询参数**：
- `days`: 查询天数（默认 30）

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "current_weight_kg": 68.5,
    "weight_change_kg": -1.5,
    "records": [
      {"date": "2024-01-01", "weight_kg": 70.0},
      {"date": "2024-01-08", "weight_kg": 69.5}
    ]
  }
}
```

#### GET /api/stats/achievements

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "unlocked": [
      {
        "type": "streak_7",
        "name": "七日坚持",
        "description": "连续打卡 7 天",
        "unlocked_at": "2024-01-15T18:30:00Z"
      }
    ],
    "locked": [
      {
        "type": "streak_30",
        "name": "月度达人",
        "description": "连续打卡 30 天",
        "progress": 7,
        "target": 30
      }
    ]
  }
}
```

### 5.7 Agent 对话模块

#### POST /api/agent/chat

**请求体**：
```json
{
  "message": "我想减脂，每周练4天",
  "thread_id": "optional-thread-id"
}
```

**响应**：SSE 流（见第九章）

#### GET /api/agent/history

**查询参数**：
- `thread_id`: 对话线程 ID（可选）
- `limit`: 返回条数（默认 50）

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "messages": [
      {
        "role": "user",
        "content": "我想减脂，每周练4天",
        "created_at": "2024-01-15T10:30:00Z"
      },
      {
        "role": "assistant",
        "content": "好的！根据你的身体数据...",
        "metadata": {
          "tool_calls": ["create_plan_tool"],
          "plan_id": "..."
        },
        "created_at": "2024-01-15T10:30:05Z"
      }
    ],
    "thread_id": "..."
  }
}
```

#### DELETE /api/agent/history

清空当前用户的对话历史

---

## 六、Agent 与待办业务融合设计

### 6.1 融合方式：同进程共享 Service

```
用户对话 "我想减脂，每周练4天"
    │
    ▼
[FastAPI /api/agent/chat] ──SSE──→ 前端
    │
    ▼
[LangGraph Agent]
    │ LLM 思考 → 选择 create_plan_tool
    ▼
[create_plan_tool]
    │ 调用 PlanService.generate_plan_from_goal(db, user_id, goal, days)
    ▼
[PlanService]
    │ 1. 读取用户身体数据
    │ 2. 根据目标+体能生成计划
    │ 3. 写入 plans + plan_days + plan_day_exercises
    ▼
[返回结构化计划 JSON]
    │
    ▼
[LLM 生成自然语言回复 + 结构化卡片数据]
    │
    ▼
[SSE 推送给前端]
```

### 6.2 数据流对比

| 操作 | REST API 路径 | Agent 路径 |
|------|---------------|------------|
| 创建计划 | 前端 → POST /api/plans → Router → PlanService → DB | 前端 → POST /api/agent/chat → Agent → create_plan_tool → PlanService → DB |
| 打卡 | 前端 → POST /api/checkins → Router → CheckinService → DB | 前端 → POST /api/agent/chat → Agent → checkin_tool → CheckinService → DB |
| 查统计 | 前端 → GET /api/stats/weekly → Router → StatsService → DB | 前端 → POST /api/agent/chat → Agent → query_stats_tool → StatsService → DB |

**两条路径最终都汇聚到 Service 层**，保证数据一致性。

### 6.3 Agent Session 管理

| 场景 | 处理方式 |
|------|----------|
| 获取 db session | Tool 内部通过 `async_session_factory()` 创建独立 session |
| 获取 user_id | 从 Agent State 中读取（chat 端点注入） |
| 事务控制 | 每个 Tool 调用独立事务，成功 commit，异常 rollback |
| 对话持久化 | LangGraph checkpointer 写 PostgreSQL `checkpoints` 表 |

### 6.4 Agent Graph 构建

```python
# agents/agent_graph.py
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_openai import ChatOpenAI

from app.config import settings
from app.database import engine
from agents.harness.prompts.system import SYSTEM_PROMPT
from agents.harness.tools import (
    create_plan_tool,
    adjust_plan_tool,
    checkin_tool,
    query_stats_tool,
    get_exercises_tool,
    get_user_profile_tool,
)

# LLM 配置
llm = ChatOpenAI(
    model=settings.AGENT_MODEL,
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL,
    temperature=settings.AGENT_TEMPERATURE,
    max_tokens=settings.AGENT_MAX_TOKENS,
    streaming=True,
)

# Tools 列表
tools = [
    create_plan_tool,
    adjust_plan_tool,
    checkin_tool,
    query_stats_tool,
    get_exercises_tool,
    get_user_profile_tool,
]

# Checkpointer（对话持久化）
checkpointer = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)

# 构建 Agent
graph = create_react_agent(
    model=llm,
    tools=tools,
    prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)

async def init_agent():
    """初始化 Agent（在 FastAPI lifespan 中调用）"""
    await checkpointer.setup()  # 创建 checkpoints 表
```

### 6.5 langgraph.json 配置

```json
{
  "dependencies": ["."],
  "graphs": {
    "fitcream_agent": "./agents/agent_graph.py:graph"
  },
  "env": ".env",
  "python_version": "3.12"
}
```

- `graphs.fitcream_agent`：`langgraph dev` 启动时加载的 graph 入口
- 开发时：`uv run langgraph dev` → Studio UI 调试
- 生产时：FastAPI 直接 import graph，不走 langgraph server

---

## 七、Agent Tools 规格

### 7.1 Tool 定义规范

每个 Tool 使用 `@tool` 装饰器定义，包含：
- 清晰的函数名（LLM 用于选择）
- 详细的 docstring（LLM 理解用途）
- 类型注解的参数
- 结构化返回值

### 7.2 create_plan_tool

```python
# agents/harness/tools/plan_tools.py
from langchain_core.tools import tool
from typing import Optional
from pydantic import BaseModel, Field

from app.database import async_session_factory
from app.services.plan_service import PlanService
from app.services.user_service import UserService

class CreatePlanInput(BaseModel):
    """创建训练计划的输入参数"""
    goal: str = Field(description="健身目标：lose_fat/gain_muscle/maintain/improve_health")
    days_per_week: int = Field(ge=1, le=7, description="每周训练天数")
    difficulty: Optional[str] = Field(
        default="beginner",
        description="难度级别：beginner/intermediate/advanced"
    )
    preferences: Optional[str] = Field(
        default=None,
        description="用户偏好说明，如'不喜欢跑步'、'没有器械'"
    )

@tool(args_schema=CreatePlanInput)
async def create_plan_tool(
    goal: str,
    days_per_week: int,
    difficulty: str = "beginner",
    preferences: Optional[str] = None,
) -> dict:
    """
    根据用户的健身目标创建个性化训练计划。
    
    当用户表达想要开始健身、减脂、增肌等意图时调用此工具。
    会考虑用户的身体数据（身高、体重、年龄）生成合适的计划。
    
    Returns:
        包含计划详情、训练日安排、推荐动作的结构化数据
    """
    async with async_session_factory() as db:
        try:
            # 获取用户信息（user_id 从 context 注入）
            user = await UserService.get_by_id(db, user_id)
            
            # 生成计划
            plan = await PlanService.generate_plan_from_goal(
                db=db,
                user_id=user_id,
                goal=goal,
                days_per_week=days_per_week,
                difficulty=difficulty,
                preferences=preferences,
                user_data={
                    "height_cm": user.height_cm,
                    "weight_kg": user.weight_kg,
                    "age": user.age,
                    "gender": user.gender,
                }
            )
            
            await db.commit()
            
            return {
                "success": True,
                "plan": {
                    "id": str(plan.id),
                    "name": plan.name,
                    "goal": plan.goal,
                    "difficulty": plan.difficulty,
                    "weeks": plan.weeks,
                    "days": [
                        {
                            "day_of_week": day.day_of_week,
                            "focus": day.focus,
                            "exercises": [
                                {
                                    "name": ex.exercise.name,
                                    "sets": ex.sets,
                                    "reps": ex.reps,
                                    "weight_kg": float(ex.weight_kg) if ex.weight_kg else None,
                                }
                                for ex in day.exercises
                            ]
                        }
                        for day in plan.days
                    ]
                },
                "message": f"已为你创建{plan.name}，每周训练{days_per_week}天"
            }
        except Exception as e:
            await db.rollback()
            return {"success": False, "error": str(e)}
```

### 7.3 checkin_tool

```python
from langchain_core.tools import tool
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import date

class ExerciseRecord(BaseModel):
    """单个动作的打卡记录"""
    name: str = Field(description="动作名称")
    sets_done: int = Field(ge=1, description="完成组数")
    reps_done: int = Field(ge=1, description="每组次数")
    weight_kg: Optional[float] = Field(default=None, description="重量（kg）")

class CheckinInput(BaseModel):
    """打卡输入参数"""
    exercises: List[ExerciseRecord] = Field(description="完成的动作列表")
    duration_min: int = Field(ge=1, description="训练时长（分钟）")
    mood: Optional[int] = Field(default=None, ge=1, le=5, description="心情评分 1-5")
    note: Optional[str] = Field(default=None, description="备注")
    checkin_date: Optional[str] = Field(default=None, description="打卡日期 YYYY-MM-DD，默认今天")

@tool(args_schema=CheckinInput)
async def checkin_tool(
    exercises: List[dict],
    duration_min: int,
    mood: Optional[int] = None,
    note: Optional[str] = None,
    checkin_date: Optional[str] = None,
) -> dict:
    """
    记录今日训练打卡。
    
    当用户说"今天练了..."、"打卡"、"完成了训练"等表达时调用。
    会解析用户描述的动作、组数、次数、重量，写入数据库。
    
    Returns:
        打卡确认信息 + 当前连续打卡天数
    """
    async with async_session_factory() as db:
        try:
            # 解析日期
            target_date = date.fromisoformat(checkin_date) if checkin_date else date.today()
            
            # 匹配动作名称到动作库
            matched_exercises = []
            for ex in exercises:
                exercise = await ExerciseService.search_by_name(db, ex["name"])
                if exercise:
                    matched_exercises.append({
                        "exercise_id": exercise.id,
                        "sets_done": ex["sets_done"],
                        "reps_done": ex["reps_done"],
                        "weight_kg": ex.get("weight_kg"),
                    })
            
            # 创建打卡记录
            checkin = await CheckinService.create_checkin(
                db=db,
                user_id=user_id,
                data={
                    "date": target_date,
                    "duration_min": duration_min,
                    "mood": mood,
                    "note": note,
                    "exercises": matched_exercises,
                }
            )
            
            # 获取连续打卡天数
            streak = await CheckinService.get_streak(db, user_id)
            
            # 检查成就解锁
            new_achievements = await AchievementService.check_and_unlock(db, user_id)
            
            await db.commit()
            
            return {
                "success": True,
                "checkin_id": str(checkin.id),
                "date": str(target_date),
                "exercises_count": len(matched_exercises),
                "duration_min": duration_min,
                "current_streak": streak["current_streak"],
                "new_achievements": [a.type for a in new_achievements],
                "message": f"打卡成功！已连续训练 {streak['current_streak']} 天 🔥"
            }
        except Exception as e:
            await db.rollback()
            return {"success": False, "error": str(e)}
```

### 7.4 query_stats_tool

```python
@tool
async def query_stats_tool(
    period: str = "weekly",
    metric: Optional[str] = None,
) -> dict:
    """
    查询训练统计数据。
    
    当用户问"这周练得怎么样"、"看看我的进度"、"统计一下"等时调用。
    
    Args:
        period: 查询周期 - weekly（本周）/ monthly（本月）/ all（全部）
        metric: 关注的指标 - workouts（训练次数）/ duration（时长）/ body（体重）
    
    Returns:
        统计数据和自然语言分析
    """
    async with async_session_factory() as db:
        if period == "weekly":
            stats = await StatsService.get_weekly_stats(db, user_id)
        elif period == "monthly":
            stats = await StatsService.get_monthly_trend(db, user_id)
        else:
            stats = await StatsService.get_all_stats(db, user_id)
        
        return {
            "success": True,
            "period": period,
            "stats": stats,
            "analysis": generate_analysis_text(stats),  # 生成分析文本
        }
```

### 7.5 get_exercises_tool

```python
@tool
async def get_exercises_tool(
    muscle_group: Optional[str] = None,
    equipment: Optional[str] = None,
    keyword: Optional[str] = None,
) -> dict:
    """
    查询健身动作库。
    
    当用户问"练胸有什么动作"、"没有器械怎么练"、"推荐一些动作"时调用。
    
    Args:
        muscle_group: 目标肌群 - chest/back/legs/shoulders/arms/core/full_body
        equipment: 器械类型 - barbell/dumbbell/machine/bodyweight/cable
        keyword: 搜索关键词
    
    Returns:
        动作列表 + 推荐组合
    """
    async with async_session_factory() as db:
        exercises = await ExerciseService.search(
            db,
            muscle_group=muscle_group,
            equipment=equipment,
            keyword=keyword,
        )
        
        return {
            "success": True,
            "count": len(exercises),
            "exercises": [
                {
                    "name": ex.name,
                    "muscle_group": ex.muscle_group,
                    "equipment": ex.equipment,
                    "difficulty": ex.difficulty,
                    "description": ex.description,
                }
                for ex in exercises[:20]  # 限制返回数量
            ],
            "recommendation": generate_recommendation(exercises, muscle_group),
        }
```

### 7.6 get_user_profile_tool

```python
@tool
async def get_user_profile_tool() -> dict:
    """
    获取当前用户的个人资料和身体数据。
    
    当需要了解用户信息以提供个性化建议时调用。
    
    Returns:
        用户基本信息、身体数据、健身目标
    """
    async with async_session_factory() as db:
        user = await UserService.get_by_id(db, user_id)
        
        return {
            "success": True,
            "profile": {
                "name": user.name,
                "height_cm": float(user.height_cm) if user.height_cm else None,
                "weight_kg": float(user.weight_kg) if user.weight_kg else None,
                "age": user.age,
                "gender": user.gender,
                "goal": user.goal,
                "bmi": calculate_bmi(user.height_cm, user.weight_kg),
            }
        }
```

### 7.7 adjust_plan_tool

```python
class AdjustPlanInput(BaseModel):
    """调整计划的输入参数"""
    plan_id: Optional[str] = Field(default=None, description="要调整的计划ID，默认当前活跃计划")
    action: str = Field(description="调整类型：add_day/remove_day/modify_exercise/change_difficulty")
    details: str = Field(description="调整详情描述")

@tool(args_schema=AdjustPlanInput)
async def adjust_plan_tool(
    action: str,
    details: str,
    plan_id: Optional[str] = None,
) -> dict:
    """
    调整现有训练计划。
    
    当用户说"太累了减一天"、"把周三改成休息"、"增加一些重量"时调用。
    
    Returns:
        调整后的计划详情 + 变更说明
    """
    async with async_session_factory() as db:
        # 获取计划（默认当前活跃计划）
        if not plan_id:
            plan = await PlanService.get_active_plan(db, user_id)
        else:
            plan = await PlanService.get_plan_detail(db, UUID(plan_id), user_id)
        
        if not plan:
            return {"success": False, "error": "没有找到需要调整的计划"}
        
        # 根据 action 执行调整
        changes = await PlanService.adjust_plan(db, plan, action, details)
        await db.commit()
        
        return {
            "success": True,
            "plan_id": str(plan.id),
            "action": action,
            "changes": changes,
            "message": f"计划已调整：{changes['summary']}"
        }
```

---

## 八、System Prompt 设计

```python
# agents/harness/prompts/system.py

SYSTEM_PROMPT = """
# 角色定义

你是 FitCream 的 AI 健身教练助手，名叫 "小健"。你的职责是帮助用户制定训练计划、记录打卡、分析进度，并提供个性化的健身建议。

# 核心能力

1. **生成训练计划**：根据用户目标（减脂/增肌/维持/健康）、体能水平、可用时间创建个性化计划
2. **调整计划**：根据用户反馈调整训练强度、频率、动作选择
3. **自然语言打卡**：解析用户描述的训练内容，记录到数据库
4. **数据分析**：查询并分析用户的训练统计，提供洞察
5. **动作推荐**：根据目标肌群、可用器械推荐合适的动作
6. **激励支持**：在用户缺乏动力时提供鼓励和个性化激励

# 行为准则

1. **真实操作**：所有承诺的操作必须通过工具真实执行，不能只是口头回复
2. **个性化**：始终考虑用户的身体数据（身高、体重、年龄、性别）给出建议
3. **循序渐进**：不要给初学者推荐过高的训练强度
4. **安全第一**：提醒用户注意热身、正确姿势，避免受伤
5. **积极正面**：保持鼓励性的语气，肯定用户的努力

# 输出格式

- 使用自然、友好的中文
- 适当使用 emoji 增加亲和力（但不要过度）
- 创建计划时返回结构化数据，前端会渲染为卡片
- 数据分析时给出具体数字和趋势解读

# 限制

- 不提供医疗建议
- 不推荐极端节食或过度训练
- 遇到无法处理的问题，诚实告知并建议咨询专业人士

# 示例对话

用户：我想减脂，每周能练4天
助手：好的！让我先了解一下你的身体数据... [调用 get_user_profile_tool]
助手：根据你的情况（175cm/75kg），我为你制定了一个4天减脂计划... [调用 create_plan_tool]
助手：计划已创建！📋 每周安排如下：
- 周一：胸部 + 有氧
- 周二：背部
- 周四：腿部
- 周五：肩部 + 核心
每个训练日结束后记得打卡哦！💪

用户：今天练了深蹲 5x5 100kg，用了45分钟
助手：[调用 checkin_tool]
助手：打卡成功！✅ 深蹲 5x5 100kg 已记录。你已经连续训练 7 天了，继续保持！🔥
"""
```

---

## 九、SSE 流式输出设计

### 9.1 事件类型

| event type | data 结构 | 说明 |
|------------|-----------|------|
| `token` | `{"content": "..."}` | LLM 逐 token 输出 |
| `tool_start` | `{"tool": "create_plan_tool", "input": {...}}` | 工具开始调用 |
| `tool_result` | `{"tool": "...", "data": {...}}` | 工具返回结构化数据（前端渲染卡片） |
| `done` | `{"usage": {...}, "thread_id": "..."}` | 对话结束 |
| `error` | `{"code": 50001, "message": "..."}` | 错误 |

### 9.2 SSE 端点实现

```python
# app/routers/agent.py
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import json
import asyncio

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.agent import ChatRequest
from agents.agent_graph import graph

router = APIRouter(prefix="/agent", tags=["agent"])

@router.post("/chat")
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Agent 对话端点（SSE 流式响应）"""
    
    async def event_generator():
        thread_id = request.thread_id or str(current_user.id)
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": str(current_user.id),  # 注入 user_id
            }
        }
        
        input_message = {"messages": [{"role": "user", "content": request.message}]}
        
        try:
            async for event in graph.astream_events(
                input_message,
                config=config,
                version="v2",
            ):
                kind = event["event"]
                
                if kind == "on_chat_model_stream":
                    # LLM token 流
                    content = event["data"]["chunk"].content
                    if content:
                        yield format_sse("token", {"content": content})
                
                elif kind == "on_tool_start":
                    # 工具开始调用
                    tool_name = event["name"]
                    yield format_sse("tool_start", {"tool": tool_name})
                
                elif kind == "on_tool_end":
                    # 工具返回结果
                    tool_name = event["name"]
                    result = event["data"].get("output", {})
                    yield format_sse("tool_result", {"tool": tool_name, "data": result})
            
            # 对话结束
            yield format_sse("done", {"thread_id": thread_id})
            
        except Exception as e:
            yield format_sse("error", {"code": 50001, "message": str(e)})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )

def format_sse(event: str, data: dict) -> str:
    """格式化 SSE 消息"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```

### 9.3 前端处理

```typescript
// frontend/src/hooks/useSSE.ts
export function useSSE() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  
  const sendMessage = async (content: string) => {
    setIsStreaming(true);
    
    const response = await fetch('/api/agent/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ message: content }),
    });
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    let currentMessage = '';
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');
      
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          const eventType = line.slice(7);
          // 处理下一行的 data
        } else if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));
          
          switch (currentEvent) {
            case 'token':
              currentMessage += data.content;
              updateLastMessage(currentMessage);
              break;
            case 'tool_result':
              // 渲染结构化卡片
              addCardMessage(data);
              break;
            case 'done':
              setIsStreaming(false);
              break;
            case 'error':
              showError(data.message);
              break;
          }
        }
      }
    }
  };
  
  return { messages, sendMessage, isStreaming };
}
```

---

## 十、认证与安全

### 10.1 JWT 实现

```python
# app/utils/security.py
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from uuid import UUID

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def hash_password(password: str) -> str:
    """密码哈希"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(user_id: UUID, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(user_id: UUID) -> str:
    """创建刷新令牌"""
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def verify_access_token(token: str) -> Optional[dict]:
    """验证访问令牌"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None

def verify_refresh_token(token: str) -> Optional[dict]:
    """验证刷新令牌"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None
```

### 10.2 认证流程

```
注册/登录 → AuthService → 返回 TokenPair(access + refresh)
    │
    ▼
前端存 localStorage
    │
    ▼
每次请求 → Authorization: Bearer <access_token>
    │
    ▼
dependencies.py: get_current_user 验证 token → 返回 User
    │
    ▼
token 过期 → 前端拦截器 → POST /api/auth/refresh → 新 token → 重试原请求
```

### 10.3 安全措施

| 项目 | 实现 |
|------|------|
| 密码存储 | bcrypt（cost=12） |
| JWT 签名 | HS256（生产环境建议 RS256） |
| Token 有效期 | access: 15min, refresh: 7d |
| API 保护 | 所有 `/api/*` 除 auth 外需 Bearer token |
| Rate limit | Agent chat 10 req/min/user |
| CORS | 配置白名单 |
| SQL 注入 | SQLAlchemy ORM 参数化查询 |
| XSS | 响应头 `Content-Type: application/json` |
| CSRF | SameSite Cookie（如使用 Cookie 存储） |

---

## 十一、错误码规范

### 11.1 错误码定义

```python
# app/utils/exceptions.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

class ErrorCode:
    # 通用
    SUCCESS = 0
    UNKNOWN_ERROR = 50000
    
    # 认证 401xx
    UNAUTHORIZED = 40100
    INVALID_TOKEN = 40101
    TOKEN_EXPIRED = 40102
    INVALID_CREDENTIALS = 40103
    
    # 权限 403xx
    FORBIDDEN = 40300
    RESOURCE_NOT_OWNED = 40301
    
    # 资源 404xx
    NOT_FOUND = 40400
    USER_NOT_FOUND = 40401
    PLAN_NOT_FOUND = 40402
    CHECKIN_NOT_FOUND = 40403
    
    # 业务 400xx
    BAD_REQUEST = 40000
    EMAIL_ALREADY_EXISTS = 40001
    CHECKIN_ALREADY_EXISTS = 40002
    INVALID_DATE = 40003
    INVALID_MOOD_RANGE = 40004
    
    # Agent 500xx
    AGENT_ERROR = 50001
    TOOL_EXECUTION_ERROR = 50002
    LLM_ERROR = 50003

class BusinessException(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

class NotFoundException(BusinessException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(ErrorCode.NOT_FOUND, message)

class UnauthorizedException(BusinessException):
    def __init__(self, message: str = "未授权"):
        super().__init__(ErrorCode.UNAUTHORIZED, message)

class ForbiddenException(BusinessException):
    def __init__(self, message: str = "无权限"):
        super().__init__(ErrorCode.FORBIDDEN, message)

def register_exception_handlers(app: FastAPI):
    """注册全局异常处理器"""
    
    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        return JSONResponse(
            status_code=200,  # 业务错误也返回 200，通过 code 区分
            content={"code": exc.code, "message": exc.message, "data": None}
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "code": ErrorCode.BAD_REQUEST,
                "message": "参数校验失败",
                "data": {"errors": exc.errors()}
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"code": ErrorCode.UNKNOWN_ERROR, "message": "服务器内部错误", "data": None}
        )
```

### 11.2 错误码速查表

| 错误码 | 含义 | HTTP Status |
|--------|------|-------------|
| 0 | 成功 | 200 |
| 40000 | 请求参数错误 | 400/422 |
| 40001 | 邮箱已注册 | 200 |
| 40002 | 今日已打卡 | 200 |
| 40003 | 无效日期（未来日期） | 200 |
| 40004 | 心情评分超出范围 | 200 |
| 40100 | 未认证 | 401 |
| 40101 | 无效令牌 | 401 |
| 40102 | 令牌过期 | 401 |
| 40103 | 邮箱或密码错误 | 200 |
| 40300 | 无权限 | 403 |
| 40301 | 资源不属于当前用户 | 403 |
| 40400 | 资源不存在 | 404 |
| 50000 | 服务器内部错误 | 500 |
| 50001 | Agent 执行错误 | 200 (SSE) |
| 50002 | 工具执行失败 | 200 (SSE) |

---

## 十二、环境变量配置

### .env.example

```bash
# 应用配置
APP_NAME=FitCream
DEBUG=true
API_PREFIX=/api

# 数据库
DATABASE_URL=postgresql+asyncpg://fitcream:fitcream@localhost:5432/fitcream
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30

# JWT
JWT_SECRET=your-super-secret-key-change-in-production-min-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# LLM / Agent
OPENAI_API_KEY=sk-your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
AGENT_MODEL=gpt-4o-mini
AGENT_TEMPERATURE=0.7
AGENT_MAX_TOKENS=2000

# CORS（逗号分隔）
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]

# Rate Limit
AGENT_RATE_LIMIT=10

# 日志
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### 配置加载

```python
# 使用 pydantic-settings 自动加载 .env
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... 配置项定义
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
```

---

## 十三、日志与监控

### 13.1 日志配置

```python
# app/utils/logger.py
import logging
import sys
from app.config import settings

def setup_logging():
    """配置日志"""
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
        if settings.LOG_FORMAT == "text"
        else '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "line": %(lineno)d, "message": "%(message)s"}'
    )
    
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            # 可添加文件 handler
            # logging.FileHandler("logs/app.log"),
        ]
    )
    
    # 降低第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
```

### 13.2 请求日志中间件

```python
# app/middleware/logging.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
import uuid

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        # 记录请求
        logger.info(f"[{request_id}] → {request.method} {request.url.path}")
        
        response = await call_next(request)
        
        # 记录响应
        duration = (time.time() - start_time) * 1000
        logger.info(f"[{request_id}] ← {response.status_code} ({duration:.2f}ms)")
        
        response.headers["X-Request-ID"] = request_id
        return response
```

### 13.3 健康检查

```python
# app/routers/health.py
from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """基础健康检查"""
    return {"status": "healthy"}

@router.get("/health/detailed")
async def detailed_health_check():
    """详细健康检查（含数据库连接）"""
    db_status = "healthy"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": "1.0.0",
    }
```

---

## 十四、测试策略

### 14.1 测试目录结构

```
tests/
├── __init__.py
├── conftest.py           ← pytest fixtures
├── test_auth.py          ← 认证测试
├── test_users.py         ← 用户模块测试
├── test_plans.py         ← 计划模块测试
├── test_checkins.py      ← 打卡模块测试
├── test_stats.py         ← 统计模块测试
├── test_agent.py         ← Agent 测试
└── test_services/        ← Service 层单元测试
    ├── test_plan_service.py
    └── test_checkin_service.py
```

### 14.2 测试 Fixtures

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.config import settings

# 测试数据库
TEST_DATABASE_URL = "postgresql+asyncpg://fitcream:fitcream@localhost:5432/fitcream_test"

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(test_engine)
    async with session_factory() as session:
        yield session
        await session.rollback()

@pytest_asyncio.fixture
async def client(test_engine):
    session_factory = async_sessionmaker(test_engine)
    
    async def override_get_db():
        async with session_factory() as session:
            yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def auth_headers(client):
    """注册并登录，返回认证头"""
    await client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "TestPass123!",
        "name": "测试用户"
    })
    response = await client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "TestPass123!"
    })
    token = response.json()["data"]["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### 14.3 测试示例

```python
# tests/test_auth.py
import pytest

@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post("/api/auth/register", json={
        "email": "new@example.com",
        "password": "SecurePass123!",
        "name": "新用户"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["user"]["email"] == "new@example.com"
    assert "access_token" in data["data"]["tokens"]

@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    # 先注册
    await client.post("/api/auth/register", json={
        "email": "dup@example.com",
        "password": "Pass123!",
    })
    
    # 重复注册
    response = await client.post("/api/auth/register", json={
        "email": "dup@example.com",
        "password": "Pass456!",
    })
    
    assert response.json()["code"] == 40001

@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={
        "email": "user@example.com",
        "password": "CorrectPass!",
    })
    
    response = await client.post("/api/auth/login", json={
        "email": "user@example.com",
        "password": "WrongPass!",
    })
    
    assert response.json()["code"] == 40103

# tests/test_checkins.py
@pytest.mark.asyncio
async def test_create_checkin(client, auth_headers):
    response = await client.post("/api/checkins", json={
        "date": "2024-01-15",
        "duration_min": 60,
        "mood": 4,
        "exercises": []
    }, headers=auth_headers)
    
    assert response.status_code == 200
    assert response.json()["code"] == 0

@pytest.mark.asyncio
async def test_checkin_future_date(client, auth_headers):
    response = await client.post("/api/checkins", json={
        "date": "2099-01-01",  # 未来日期
        "duration_min": 60,
    }, headers=auth_headers)
    
    assert response.json()["code"] == 40003

@pytest.mark.asyncio
async def test_checkin_duplicate(client, auth_headers):
    # 第一次打卡
    await client.post("/api/checkins", json={
        "date": "2024-01-15",
        "duration_min": 60,
    }, headers=auth_headers)
    
    # 同一天重复打卡
    response = await client.post("/api/checkins", json={
        "date": "2024-01-15",
        "duration_min": 30,
    }, headers=auth_headers)
    
    assert response.json()["code"] == 40002
```

### 14.4 运行测试

```bash
# 运行所有测试
cd rogers
uv run pytest

# 运行特定文件
uv run pytest tests/test_auth.py -v

# 带覆盖率
uv run pytest --cov=app --cov-report=html

# 只运行异步测试
uv run pytest -m asyncio
```

---

## 十五、性能优化

### 15.1 数据库连接池

```python
# 连接池配置
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,           # 连接池大小
    max_overflow=20,        # 最大溢出连接数
    pool_timeout=30,        # 获取连接超时
    pool_recycle=3600,      # 连接回收时间（秒）
    pool_pre_ping=True,     # 连接前 ping 检测
)
```

### 15.2 查询优化

```python
# 使用 selectin 预加载关联数据
class Plan(Base):
    days: Mapped[List["PlanDay"]] = relationship(
        back_populates="plan",
        lazy="selectin",  # 自动预加载
    )

# 分页查询使用 keyset pagination（大数据量）
async def list_checkins_keyset(db, user_id, cursor_date, limit):
    query = (
        select(Checkin)
        .where(Checkin.user_id == user_id)
        .where(Checkin.date < cursor_date)
        .order_by(Checkin.date.desc())
        .limit(limit)
    )
    return await db.execute(query)
```

### 15.3 缓存策略

```python
# 动作库缓存（变化频率低）
from functools import lru_cache
from typing import Dict, List

_exercise_cache: Dict[str, List] = {}

async def get_exercises_by_muscle(db, muscle_group: str):
    cache_key = f"exercises:{muscle_group}"
    if cache_key in _exercise_cache:
        return _exercise_cache[cache_key]
    
    result = await db.execute(
        select(Exercise).where(Exercise.muscle_group == muscle_group)
    )
    exercises = result.scalars().all()
    _exercise_cache[cache_key] = exercises
    return exercises
```

### 15.4 异步任务

```python
# 成就检测异步执行（不阻塞主流程）
import asyncio

async def create_checkin_with_achievement(db, user_id, data):
    checkin = await CheckinService.create_checkin(db, user_id, data)
    await db.commit()
    
    # 异步检测成就（不等待）
    asyncio.create_task(
        AchievementService.check_and_unlock(db, user_id)
    )
    
    return checkin
```

---

## 十六、部署架构

### 16.1 开发环境

```bash
# 终端 1：FastAPI
cd rogers && uv run uvicorn app.main:app --reload --port 8000

# 终端 2：LangGraph Studio（可选，调试 Agent）
cd rogers && uv run langgraph dev

# 终端 3：前端
cd frontend && pnpm dev
```

### 16.2 生产环境（Docker Compose）

```yaml
# docker-compose.yml
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: fitcream
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: fitcream
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fitcream"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  rogers:
    build:
      context: ./rogers
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://fitcream:${DB_PASSWORD}@postgres:5432/fitcream
      JWT_SECRET: ${JWT_SECRET}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      DEBUG: "false"
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    command: uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - rogers
    restart: unless-stopped

volumes:
  pgdata:
```

### 16.3 Dockerfile（后端）

```dockerfile
# rogers/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 安装依赖
RUN uv sync --frozen --no-dev

# 复制代码
COPY . .

# 运行
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 16.4 架构图

```
┌──────────────────────────────────────────┐
│  docker-compose.yml                      │
│                                          │
│  postgres:16  ←──  rogers (FastAPI)     │
│       ↑              │                   │
│       │              └── agents/graph    │
│       │                  (同进程)        │
│       │                                  │
│  frontend (nginx + React build)          │
└──────────────────────────────────────────┘
```

**生产模式不需要单独启动 langgraph server**，Agent graph 作为 FastAPI 进程内的模块直接调用。

---

## 十七、开发指南

### 17.1 环境准备

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 后端依赖
cd rogers
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际配置

# 前端依赖
cd frontend
pnpm install
```

### 17.2 数据库迁移

```bash
cd rogers

# 生成迁移文件
uv run alembic revision --autogenerate -m "add user table"

# 执行迁移
uv run alembic upgrade head

# 回滚
uv run alembic downgrade -1

# 查看当前版本
uv run alembic current

# 查看迁移历史
uv run alembic history
```

### 17.3 种子数据

```bash
cd rogers

# 灌入动作库
uv run python seeds/seed.py

# 或使用 psql
psql -U fitcream -d fitcream -f seeds/exercises.sql
```

### 17.4 开发命令

```bash
# 后端开发服务器
cd rogers
uv run uvicorn app.main:app --reload --port 8000

# LangGraph Agent 调试
uv run langgraph dev

# 前端开发服务器
cd frontend
pnpm dev

# 运行测试
cd rogers
uv run pytest -v

# 代码检查
uv run ruff check .
uv run mypy app/
```

### 17.5 API 文档

启动后端后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 十八、关键依赖

| 包 | 版本 | 用途 |
|----|------|------|
| fastapi | ^0.115 | Web 框架 |
| uvicorn[standard] | ^0.32 | ASGI 服务器 |
| sqlalchemy[asyncio] | ^2.0 | ORM |
| asyncpg | ^0.30 | PostgreSQL 异步驱动 |
| alembic | ^1.14 | 数据库迁移 |
| pydantic | ^2.9 | 数据校验 |
| pydantic-settings | ^2.6 | 配置管理 |
| python-jose[cryptography] | ^3.3 | JWT |
| passlib[bcrypt] | ^1.7 | 密码哈希 |
| langgraph | ^0.4 | Agent 框架 |
| langchain-openai | ^0.3 | LLM 接入 |
| langgraph-checkpoint-postgres | ^2.0 | 对话持久化 |
| sse-starlette | ^2.1 | SSE 响应 |
| httpx | ^0.28 | HTTP 客户端（测试） |
| pytest | ^8.3 | 测试框架 |
| pytest-asyncio | ^0.24 | 异步测试 |

### pyproject.toml

```toml
[project]
name = "rogers"
version = "0.1.0"
description = "FitCream Backend API"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "langgraph>=0.4.0",
    "langchain-openai>=0.3.0",
    "langgraph-checkpoint-postgres>=2.0.0",
    "sse-starlette>=2.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.28.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## 十九、开发里程碑（M1-M3）

| 阶段 | 任务 | 产出 | 预计时间 |
|------|------|------|----------|
| **M1.1** | config + database + Base model | 可连接 DB | 0.5d |
| **M1.2** | User model + AuthService + auth router | 注册登录可用 | 1d |
| **M1.3** | JWT 依赖 + users router | /users/me 可用 | 0.5d |
| **M2.1** | Exercise model + 种子数据 | 动作库就绪 | 0.5d |
| **M2.2** | Plan models + PlanService + plans router | 计划 CRUD | 1.5d |
| **M2.3** | Checkin models + CheckinService + checkins router | 打卡 CRUD | 1d |
| **M2.4** | StatsService + stats router | 统计接口 | 1d |
| **M3.1** | Agent graph + state + prompt | Agent 骨架 | 0.5d |
| **M3.2** | Tools（plan/checkin/stats） | Agent 能调 Service | 1.5d |
| **M3.3** | agent router（SSE） | 前端可对话 | 1d |
| **M3.4** | 联调 + 测试 | 端到端验证 | 1d |

### 验收检查清单

- [ ] 注册 → 登录 → 获取 token → 访问 /users/me
- [ ] Token 过期后 refresh 无感续期
- [ ] 创建计划 → 添加训练日 → 查询详情
- [ ] 打卡 → 查询连续天数
- [ ] Agent 对话生成计划 → 数据库有记录
- [ ] Agent 自然语言打卡 → 数据库有记录
- [ ] SSE 流式输出（浏览器 Network 可见 event-stream）
- [ ] Docker Compose 一键启动