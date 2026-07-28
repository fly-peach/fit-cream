# fitme 模块代码优化

**日期**：2026-07-28

**来源**：代码审查

**详情**：全量审查 `rogers/src/fitme/` 下 services/、models/、schemas/ 共 25 个 Python 文件，发现 25 项优化点。

## 待办

### High

- [x] `services/stats_service.py:52-59` - N+1 查询：循环中逐条查询 CheckinExercise -> 批量 IN 查询
- [x] `services/diet_plan_service.py:368-398` - 缺失批量操作：generate 方法逐日 flush() -> uuid4() 客户端赋 ID 合并一次 flush
- [x] `services/plan_service.py:284-291` - 生成空计划：generate_plan_from_goal 的 PlanDay 不含 PlanDayExercise -> 按肌群查询动作库填充
- [x] `services/checkin_service.py:136-154` - 字段被忽略：update_checkin 不处理 exercises 字段 -> 增加 exercises 替换逻辑
- [x] `services/stats_service.py:192-195` - 全表加载：get_all_stats 拉全部 checkins 到内存 -> 用 func.count/func.sum
- [x] `services/checkin_service.py:163-167` - 全量日期加载：get_streak 加载全部日期 -> SQL 窗口函数计算 longest + 100 天有界查 current
- [x] `models/exercise.py:28-33` - 缺失索引：equipment、difficulty 无索引 -> 加索引
- [x] `services/plan_service.py` + `diet_plan_service.py` - 所有权校验重复：多处理 3 级联查未抽取 -> 提取 _verify_*_ownership helper
- [x] `services/checkin_service.py:145-150` - 部分更新不一致：手动 if x is not None -> model_dump(exclude_unset=True)
- [x] `schemas/checkin.py:50-60` - 缺失 validator：CheckinExerciseOut.exercise_name 无自动填充 -> 添加 ExerciseBrief + model_validator

### Medium

- [x] `services/stats_service.py:201` - 延迟导入：方法体内 import -> 移到模块顶部
- [x] `services/plan_service.py` vs `diet_plan_service.py` - 删除策略不统一：物理删除 vs 软删除 -> PlanService.delete_plan 改为软删除
- [x] `services/checkin_service.py:34,38` - 硬编码错误码：裸整数 40002/40003 -> ErrorCode 常量
- [x] `services/stats_service.py` - 返回类型不明确：全部返回 -> dict -> TypedDict
- [x] `services/stats_service.py:119-154` - Python 侧分组：周分组用 Python 循环 -> SQL func.floor(extract) + GROUP BY
- [x] `services/stats_service.py:176` - 异常处理不一致：get_body_trend 返回 {"success": False} -> 抛出 NotFoundException
- [x] `models/conversation.py:34` - JSONB 无 GIN 索引：metadata_json -> 加 GIN 索引
- [x] `models/thread_usage.py` + `thread_meta.py` - 字段重复定义：user_id/thread_id -> 提取 ThreadBase 混入
- [x] `models/achievement.py:18-40` - 缺少显示字段：仅存 type -> 补充 name/description/icon
- [x] `services/diet_plan_service.py:368` - 硬编码天数：generate 固定 7 天 -> days_per_week 参数化

### Low

- [x] `models/checkin.py:32-33` - 冗余索引：单列索引与复合唯一索引重叠 -> 移除 user_id 单列索引
- [x] `models/plan.py:102` - 隐式 eager load：lazy="selectin" 序列化时大 IN -> get_plan_detail 显式 selectinload
- [x] `services/exercise_service.py:58-85` - 无分页：search 有 limit 无 offset -> 添加 offset 参数 + 路由层暴露
- [x] `services/plan_service.py:120-136` - 未显式 eager load：get_plan_detail -> 加 selectinload 选项
- [x] `services/checkin_service.py:52-60` - 未预校验 foreign key：create_checkin -> 批量预校验 exercise_id 存在性
