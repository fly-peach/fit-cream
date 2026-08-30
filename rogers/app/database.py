"""
异步数据库引擎、Session 工厂、声明式基类

- engine: 全局 AsyncEngine（连接池配置来自 settings）
- async_session_factory: async_sessionmaker 工厂，供 Service 层和 Agent Tools 使用
- Base: SQLAlchemy DeclarativeBase，所有 ORM Model 继承此类
- get_db: FastAPI 依赖注入，自动管理 session 生命周期（commit/rollback/close）
- init_db: 开发环境自动建表（DEBUG=True 时）
"""
import logging
from typing import AsyncGenerator

from sqlalchemy import String, inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger("fitcream")

# 异步引擎
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
    echo=False,
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


def _column_default_literal(col) -> str | None:
    """返回列默认值的 SQL 字面量（用于 ALTER ADD COLUMN NOT NULL 时填充存量行）。"""
    if col.default is not None and getattr(col.default, "is_scalar", False):
        val = col.default.arg
        if isinstance(val, bool):
            return "TRUE" if val else "FALSE"
        if isinstance(val, (int, float)):
            return str(val)
        return "'" + str(val).replace("'", "''") + "'"
    if col.server_default is not None:
        try:
            return col.server_default.arg.text
        except AttributeError:
            return None
    return None


def _add_missing_columns(sync_conn, logger_=None) -> list[str]:
    """对已存在的表，补齐模型中新增但数据库缺失的列（DEBUG 便利，幂等）。

    单列 ALTER 失败仅告警不中断：如托管 PG 无 pgvector 扩展时，
    exercises.embedding 的 VECTOR 列 ALTER 会失败，不应阻塞其余补列与启动。
    """
    insp = inspect(sync_conn)
    existing_tables = set(insp.get_table_names())
    added: list[str] = []
    for table_name, table_obj in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue
        existing_cols = {c["name"] for c in insp.get_columns(table_name)}
        for col in table_obj.columns:
            if col.name in existing_cols:
                continue
            type_sql = col.type.compile(dialect=sync_conn.dialect)
            if col.nullable:
                sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {type_sql} NULL'
            else:
                default_sql = _column_default_literal(col)
                if default_sql is not None:
                    sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {type_sql} NOT NULL DEFAULT {default_sql}'
                else:
                    sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {type_sql} NULL'
            try:
                # SAVEPOINT 隔离：单列 ALTER 失败（如缺 pgvector 扩展）回滚到保存点，
                # 不污染外层事务，其余列可继续补齐
                with sync_conn.begin_nested():
                    sync_conn.execute(text(sql))
                added.append(f"{table_name}.{col.name}")
            except Exception as e:
                if logger_:
                    logger_.warning(f"补列失败 {table_name}.{col.name}（功能降级）: {e}")
                else:
                    raise
    return added


def _relax_not_null_columns(sync_conn, logger_=None) -> list[str]:
    """对模型已改 nullable 但数据库仍 NOT NULL 的既有列，放宽约束（DEBUG 便利，幂等）。

    _add_missing_columns 只补新列，不会改既有列约束；模型演进后（如有氧动作无组次、
    动作勾选建卡时总时长未知）需放宽存量列。先 inspect 判断当前是否仍 NOT NULL，
    是则执行 DROP NOT NULL；单列失败 SAVEPOINT 隔离仅告警不中断（与补列风格一致）。
    """
    relax_targets = [
        ("checkin_exercises", "exercise_id"),
        ("checkins", "duration_min"),
        ("plan_day_exercises", "sets"),
        ("plan_day_exercises", "reps"),
    ]
    insp = inspect(sync_conn)
    existing_tables = set(insp.get_table_names())
    relaxed: list[str] = []
    for table_name, col_name in relax_targets:
        if table_name not in existing_tables:
            continue
        col_info = next(
            (c for c in insp.get_columns(table_name) if c["name"] == col_name),
            None,
        )
        if col_info is None or col_info.get("nullable", True):
            continue
        sql = f'ALTER TABLE "{table_name}" ALTER COLUMN "{col_name}" DROP NOT NULL'
        try:
            with sync_conn.begin_nested():
                sync_conn.execute(text(sql))
            relaxed.append(f"{table_name}.{col_name}")
        except Exception as e:
            if logger_:
                logger_.warning(f"放宽 NOT NULL 失败 {table_name}.{col_name}（功能降级）: {e}")
            else:
                raise
    return relaxed


def _ensure_custom_food_fk_sets_null(sync_conn, logger_=None) -> list[str]:
    """确保 diet_meals.custom_food_item_id 外键为 ON DELETE SET NULL（防删除自定义食物级联清空饮食历史）。

    现状 FK 为默认 NO ACTION（无 ondelete），配合 ORM 端 delete-orphan 会连删历史餐；
    模型已移除 delete-orphan 并声明 ondelete=SET NULL，此处把存量约束重建为 SET NULL（幂等）。
    """
    if "diet_meals" not in set(inspect(sync_conn).get_table_names()):
        return []
    rows = sync_conn.execute(text(
        "SELECT conname FROM pg_constraint"
        " WHERE conrelid = 'diet_meals'::regclass AND contype = 'f'"
        "   AND pg_get_constraintdef(oid) ILIKE '%custom_food_items%'"
    )).fetchall()
    changed: list[str] = []
    for (conname,) in rows:
        defn = sync_conn.execute(
            text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :n"),
            {"n": conname},
        ).scalar()
        if defn and "ON DELETE SET NULL" in defn:
            continue
        try:
            with sync_conn.begin_nested():
                sync_conn.execute(text(
                    f'ALTER TABLE "diet_meals" DROP CONSTRAINT "{conname}"'
                ))
                sync_conn.execute(text(
                    'ALTER TABLE "diet_meals" ADD CONSTRAINT "fk_diet_meals_custom_food_item"'
                    ' FOREIGN KEY ("custom_food_item_id") REFERENCES "custom_food_items" ("id")'
                    ' ON DELETE SET NULL'
                ))
            changed.append(conname)
        except Exception as e:
            if logger_:
                logger_.warning(f"重建自定义食物外键失败 {conname}（功能降级）: {e}")
            else:
                raise
    return changed


_GOAL_ARCHETYPE_V2_DDL = (
    "ALTER TABLE goal_archetypes"
    " ADD COLUMN IF NOT EXISTS gender VARCHAR(10) NOT NULL DEFAULT 'male',"
    " ADD COLUMN IF NOT EXISTS image VARCHAR(300),"
    " ADD COLUMN IF NOT EXISTS target_exercises"
    " JSONB NOT NULL DEFAULT '[]'::jsonb,"
    " ADD COLUMN IF NOT EXISTS target_exercise_goal"
    " JSONB NOT NULL DEFAULT '[]'::jsonb",
    "DELETE FROM goal_archetypes",
    "ALTER TABLE goal_archetypes"
    " ALTER COLUMN stage_hint TYPE VARCHAR(50) USING stage_hint::text,"
    " ALTER COLUMN stage_narrative_hint TYPE TEXT"
    " USING stage_narrative_hint::text",
    "ALTER TABLE goal_archetypes DROP COLUMN IF EXISTS female_only",
    "ALTER TABLE goal_archetypes"
    " DROP CONSTRAINT IF EXISTS goal_archetypes_key_key",
    "ALTER TABLE goal_archetypes"
    " DROP CONSTRAINT IF EXISTS uq_goal_archetypes_key_gender",
    "ALTER TABLE goal_archetypes"
    " ADD CONSTRAINT uq_goal_archetypes_key_gender UNIQUE (key, gender)",
)


def _ensure_goal_archetypes_v2(sync_conn, logger_=None) -> bool:
    """把 goal_archetypes 存量表收敛到 v2 结构（一行=(key,gender)，幂等）。

    与 scripts/migrations/2026-08-30_goal_archetype_v2.sql 对齐：补列 -> 清行
    （种子重灌，JSON 为唯一真源）-> stage 列类型收敛 -> 下线 female_only 与
    key 单列唯一约束 -> 建 (key,gender) 唯一约束。仅当检测到旧结构时执行；
    新库由 create_all 直接建出 v2 结构，无需处理。
    init_db（DEBUG）与测试 conftest 共用本函数；生产走迁移 SQL。
    """
    if "goal_archetypes" not in set(inspect(sync_conn).get_table_names()):
        return False
    cols = {c["name"]: c["type"] for c in inspect(sync_conn).get_columns("goal_archetypes")}
    needs_migration = (
        "gender" not in cols
        or "female_only" in cols
        or not isinstance(cols.get("stage_hint"), String)
    )
    if not needs_migration:
        return False
    for sql in _GOAL_ARCHETYPE_V2_DDL:
        sync_conn.execute(text(sql))
    return True


def _ensure_enum_check_constraints(sync_conn, logger_=None) -> list[str]:
    """为枚举字符串列补 CHECK 约束（幂等，单条失败仅告警不中断）。

    存量若存在非法枚举值会导致本条 ADD CONSTRAINT 失败（SAVEPOINT 回滚），
    需先清数据；不影响其余约束与启动。
    """
    checks = [
        ("users", "gender", "('male','female','other')"),
        ("users", "role", "('user','admin')"),
        ("plans", "status", "('active','archived','completed')"),
        ("plans", "difficulty", "('beginner','intermediate','advanced')"),
        ("plans", "goal", "('lose_fat','gain_muscle','maintain','improve_health')"),
        ("diet_plans", "status", "('active','archived')"),
        ("diet_plans", "goal", "('lose_fat','gain_muscle','maintain','improve_health')"),
        ("user_goals", "goal", "('lose_fat','gain_muscle','maintain','improve_health')"),
        ("diet_meals", "meal_type", "('breakfast','lunch','dinner','snack')"),
        ("diet_plan_meals", "meal_type", "('breakfast','lunch','dinner','snack')"),
        ("plan_day_exercises", "exercise_type", "('strength','cardio')"),
        ("health_metrics", "bmi_status", "('偏瘦','正常','偏胖','肥胖')"),
        ("user_fitness_profiles", "parq_result", "('low','uncertain','high')"),
        (
            "user_fitness_profiles",
            "training_experience",
            "('never','beginner','intermediate','advanced')",
        ),
        ("user_fitness_profiles", "cardio_level", "('beginner','intermediate','advanced')"),
        ("user_fitness_profiles", "strength_level", "('beginner','intermediate','advanced')"),
        ("user_fitness_profiles", "flexibility", "('limited','normal','good')"),
        ("user_fitness_profiles", "weekly_frequency", "('0','1-2','3-4','5+')"),
        ("user_fitness_profiles", "session_duration", "('<30','30-60','>60')"),
        ("user_fitness_profiles", "sleep_quality", "('poor','normal','good')"),
        ("user_fitness_profiles", "stress_level", "('low','medium','high')"),
        ("user_fitness_profiles", "preferred_time", "('morning','noon','evening','flexible')"),
        ("user_fitness_profiles", "meals_per_day", "('2','3','4','5+')"),
        ("user_fitness_profiles", "eating_out_ratio", "('mostly_out','half','mostly_home')"),
    ]
    existing_tables = set(inspect(sync_conn).get_table_names())
    added: list[str] = []
    for table, col, values in checks:
        if table not in existing_tables:
            continue
        conname = f"ck_{table}_{col}"
        sql = (
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{conname}"'
            f" CHECK (\"{col}\" IS NULL OR \"{col}\" IN {values})"
        )
        try:
            with sync_conn.begin_nested():
                sync_conn.execute(text(sql))
            added.append(f"{table}.{col}")
        except Exception as e:
            if logger_:
                logger_.warning(f"枚举 CHECK 约束失败 {table}.{col}（约束降级）: {e}")
            else:
                raise
    return added


# 初始化数据库（开发环境自动建表）
async def init_db() -> None:
    if not settings.DEBUG:
        return

    import app.models  # noqa: F401 导入所有 model（注册到 Base.metadata）

    async with engine.begin() as conn:
        # pgvector 扩展：exercises.embedding 向量列依赖（须早于 create_all / 补列执行；
        # 记忆子系统的 MemoryStore.init_db 也会创建，此处保证先后顺序无关）。
        # SAVEPOINT 隔离：语句失败仅回滚到保存点，不中止外层事务（否则后续语句全部报
        # InFailedSQLTransaction）。扩展不可用时不做降级：embedding 列不会被创建，
        # 语义检索功能整体关闭（ExerciseService 探测到列缺失返回空，工具回退关键词检索）；
        # embedding 为 deferred 列，常规查询不引用它，缺列不影响其他功能。
        try:
            async with conn.begin_nested():
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception as e:
            logger.warning(f"pgvector 扩展不可用（动作语义检索功能关闭）: {e}")

        existing = await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )
        tables = Base.metadata.tables.keys()
        new_tables = [t for t in tables if t not in existing]

        if new_tables:
            await conn.run_sync(Base.metadata.create_all)
            logger.info(f"数据库建表完成: {', '.join(new_tables)}")
        else:
            logger.info("数据库表已存在，跳过建表")

        # 自动补齐已有表缺失的列（DEBUG 便利：模型新增列后无需手写迁移）
        added_columns = await conn.run_sync(lambda sc: _add_missing_columns(sc, logger))
        if added_columns:
            logger.info(f"数据库补列完成: {', '.join(added_columns)}")

        # 放宽模型已改 nullable 的既有列的 NOT NULL 约束（补列不改约束，需单独处理）
        relaxed_columns = await conn.run_sync(
            lambda sc: _relax_not_null_columns(sc, logger)
        )
        if relaxed_columns:
            logger.info(f"数据库放宽 NOT NULL 完成: {', '.join(relaxed_columns)}")

        # 重建 diet_meals.custom_food_item_id 外键为 ON DELETE SET NULL（幂等）
        fk_changed = await conn.run_sync(
            lambda sc: _ensure_custom_food_fk_sets_null(sc, logger)
        )
        if fk_changed:
            logger.info("数据库自定义食物外键重建为 SET NULL: %s", ", ".join(fk_changed))

        # goal_archetypes v2 结构收敛（幂等，仅检测到旧结构时执行；与迁移 SQL 对齐）
        migrated = await conn.run_sync(
            lambda sc: _ensure_goal_archetypes_v2(sc, logger)
        )
        if migrated:
            logger.info("goal_archetypes v2 结构收敛完成")

        # pg_trgm 扩展 + GIN trigram 索引：加速 exercises 的中文/英文 ilike 关键词搜索
        # CREATE EXTENSION 在托管 PG 上可能需 superuser 权限，失败时兜底降级为全表扫。
        # SAVEPOINT 隔离：否则语句失败中止事务，最终 commit 变 rollback，
        # 前面 create_all/补列的 DDL 会被整体回滚。
        try:
            async with conn.begin_nested():
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
                await conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_exercises_name_trgm"
                    " ON exercises USING gin (name gin_trgm_ops)"
                ))
                await conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_exercises_name_en_trgm"
                    " ON exercises USING gin (name_en gin_trgm_ops)"
                ))
                await conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_exercises_desc_trgm"
                    " ON exercises USING gin (description gin_trgm_ops)"
                ))
                await conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_exercises_instr_trgm"
                    " ON exercises USING gin (instructions gin_trgm_ops)"
                ))
            logger.info("pg_trgm 扩展与 GIN 索引就绪")
        except Exception as e:
            logger.warning(f"pg_trgm 索引创建失败（搜索将退化为全表扫）: {e}")

        # 用户数据模型优化新增索引（幂等；对已有表 create_all 不建索引，需显式 DDL）。
        # 部分唯一索引依赖「同一用户仅一个 active 计划」的数据前提，若存量存在多 active
        # 会创建失败（SAVEPOINT 隔离，仅告警不影响启动）；须先跑归档脚本再重启。
        try:
            async with conn.begin_nested():
                await conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_health_metric_user_date"
                    " ON health_metrics (user_id, measure_date)"
                ))
                await conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_diet_meal_user_date"
                    " ON diet_meals (user_id, meal_date)"
                ))
                await conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_plan_active"
                    " ON plans (user_id) WHERE status = 'active'"
                ))
                await conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_diet_plan_active"
                    " ON diet_plans (user_id) WHERE status = 'active'"
                ))
            logger.info("用户数据模型优化索引就绪")
        except Exception as e:
            logger.warning(f"用户数据模型优化索引创建失败（约束降级）: {e}")

        # 枚举字符串 CHECK 约束（幂等；存量非法值会使单条失败，仅告警）
        enum_checks = await conn.run_sync(
            lambda sc: _ensure_enum_check_constraints(sc, logger)
        )
        if enum_checks:
            logger.info(f"数据库枚举 CHECK 约束就绪: {', '.join(enum_checks)}")
