"""
API 路由汇总

将所有子路由注册到统一的 api_router，
由 main.py 以 settings.API_PREFIX（默认 /api）前缀挂载。

子路由：
- auth: 注册/登录/刷新 Token
- users: 用户资料 CRUD
- chat: AI 对话（SSE 流式）+ 线程管理
- plans: 训练计划 CRUD
- diet_plans: 饮食计划 CRUD
- diet_meals: 饮食记录 CRUD + 每日营养汇总 + 自定义食物
- checkins: 打卡记录 CRUD + 连续打卡统计
- stats: 训练数据统计
- exercises: 动作库查询
- knowledge_bases: 知识库管理（CRUD + 搜索 + 图谱 + 成员 + 令牌 + lint）
- memory: 语义记忆只读查询
"""
from fastapi import APIRouter

from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.checkins import router as checkins_router
from app.routers.diet_meals import router as diet_meals_router
from app.routers.diet_plans import router as diet_plans_router
from app.routers.exercises import router as exercises_router
from app.routers.knowledge_bases import router as knowledge_bases_router
from app.routers.memory import router as memory_router
from app.routers.plans import router as plans_router
from app.routers.stats import router as stats_router
from app.routers.users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(chat_router)
api_router.include_router(plans_router)
api_router.include_router(diet_plans_router)
api_router.include_router(diet_meals_router)
api_router.include_router(checkins_router)
api_router.include_router(stats_router)
api_router.include_router(exercises_router)
api_router.include_router(knowledge_bases_router)
api_router.include_router(memory_router)
