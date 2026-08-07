# 工具系统

## 设计原则

所有 Agent 工具使用 LangChain `@tool` 装饰器定义，遵循以下设计原则：

- **同进程直调**：工具直接调用 Service 层方法，不走 HTTP
- **独立会话**：每个工具使用 `async_session_factory()` 创建独立数据库会话
- **RunnableConfig 注入**：从配置中提取 `user_id` 和 `thread_id`
- **结构化返回**：返回带 `success` 标志的 dict

## 工具分组

多个工具组在 `create_fitcream_agent()` 中按序加载，任意组加载失败时从略。

### 业务工具

由 `harness/tools/__init__.py` 聚合导出，共 18 个工具（业务 CRUD + 展示/推进节点）：

| 工具 | 功能 | 调用的 Service |
|------|------|---------------|
| list_plans_tool | 列出用户的所有训练计划 | PlanService.list_plans() |
| get_plan_detail_tool | 查看计划详情（含训练日/动作ID） | PlanService.get_plan_detail() |
| create_plan_tool | 创建训练计划（支持逐日结构直落库 / 模板生成） | PlanService.create_plan() / generate_plan_from_goal() |
| create_diet_plan_tool | 创建饮食计划（自动估算热量） | DietPlanService.generate_diet_plan_from_goal() |
| update_plan_tool | 更新计划元信息（名称/目标/难度/周期） | PlanService.update_plan() |
| delete_plan_tool | 归档计划（软删除） | PlanService.delete_plan() |
| add_plan_day_tool | 增加训练日（按星期） | PlanService.add_plan_day() |
| remove_plan_day_tool | 删除训练日（按星期） | PlanService.delete_plan_day() |
| sync_plan_day_tool | 同步训练日（把源星期整体复制到目标星期） | PlanService.copy_plan_day() |
| add_exercise_tool | 为训练日添加动作 | PlanService.add_exercise_to_day() |
| update_exercise_tool | 修改动作 | PlanService.update_exercise() |
| remove_exercise_tool | 删除动作 | PlanService.delete_exercise() |
| checkin_tool | 记录训练打卡 | CheckinService.create_checkin() + ExerciseService.search_by_name() |
| get_streak_tool | 查询连续打卡天数 | CheckinService.get_streak() |
| query_stats_tool | 查询训练统计数据 | StatsService（多维度） |
| get_exercises_tool | 搜索动作库 | ExerciseService.search() |
| get_user_profile_tool | 获取用户身体数据 | UserService.get_by_id() |
| update_user_profile_tool | 更新用户个人资料 | UserService.update_profile() |

#### 关键工具逻辑

- **create_plan_tool**：接收 goal、days_per_week、difficulty、preferences，以及可选的 `name`/`weeks`/`days`。**两条路径**：
  - 提供 `days`（计划设计待办队列流程产出的 `PlanDayCreate` 列表）时，直接按 agent 逐日设计的结构落库（`PlanService.create_plan`），确保提案与落库一致，跳过后端模板生成
  - 未提供 `days` 时，从 User 模型拉取身体数据（身高、体重、年龄、性别），经 `generate_plan_from_goal()` 后端模板智能生成（向后兼容）
- **create_diet_plan_tool**：接收 goal、target_calories（可选）、preferences。未提供 target_calories 时根据用户体重自动估算：减脂为 weight×22，增肌为 weight×33，维持为 weight×28
- **sync_plan_day_tool**：接收 source_day_of_week、target_day_of_week、plan_id（可选）。源训练日不存在抛错；目标日不存在则新建，存在则清空动作后覆盖为源日动作
- **checkin_tool**：接收用户输入的动作名称列表，通过 ExerciseService.search_by_name() 模糊匹配动作库中的标准动作
- **query_stats_tool**：内置多维度叙事分析（周频次建议、月均情绪、体脂趋势、里程碑识别）

### 计划设计待办队列工具（纯展示/推进节点）

由 `harness/tools/plan/plan_queue_tools.py` 定义，共 3 个工具。均为纯展示/推进节点：**不落库、不中断、无副作用**，仅作为 ReAct 步骤流中的标记节点。前端按工具名特判渲染对应卡片，读取工具入参（而非返回值）。队列状态不进 agent state_schema，由消息历史中的工具调用承载，`PlanQueueMiddleware` 每轮 `before_model` 从历史重建快照注入给模型。

| 工具 | 功能 | 返回 |
|------|------|------|
| present_plan_queue_tool | 渲染「计划设计待办队列」大纲 + 逐日待办（前端顶部常驻进度面板） | {"ok": True} |
| present_day_design_tool | 渲染单日训练方案提案（动作表格 + 设计依据 + 确认按钮） | {"ok": True} |
| update_plan_queue_item_tool | 更新队列某一项状态（pending→in_progress→completed/skipped），入参 `queue` 必须为更新后的完整快照 | {"ok": True} |

数据模型（`PlanQueue`）：goal、training_type（fat_loss/muscle_gain/recomp/cardio_only/maintain）、weekly_frequency、difficulty、phases[]（phase_id、phase_title、weeks、todos[]）。`PlanQueueTodo` 含 id、title、status、day_type、day_design（completed 后填充）；`DayDesign` 含 day_of_week、focus、day_type、exercises[]、rationale。

### 记忆工具

由 `harness/tools/memory/memory_tools.py` 定义，共 5 个工具：

| 工具 | 功能 | 底层方法 |
|------|------|----------|
| recall_memory | 多类型记忆检索 | MemoryStore.retrieve_episodic() + search_semantic() + retrieve_procedural() |
| save_preference | 保存用户偏好 | MemoryStore.store_semantic(category="preference") |
| save_user_fact | 保存用户事实/状态/规则 | MemoryStore.store_semantic() |
| list_user_profile | 列出所有存储的用户信息 | MemoryStore.retrieve_semantic() |
| save_event | 记录重要事件 | MemoryStore.store_episodic(type="event") |

### 知识库工具

由 `harness/tools/knowledge/knowledge_tools.py` 定义，共 2 个工具：

| 工具 | 功能 | 调用的 Service |
|------|------|---------------|
| search_knowledge_base | 语义搜索已订阅知识库 | KnowledgeBaseService.search_documents() |
| read_kb_document | 读取知识库文档全文 | KnowledgeBaseService.get_document() |

search_knowledge_base 的搜索范围受用户的订阅列表限制，仅搜索用户已订阅的知识库。read_kb_document 返回文档的完整标题、内容、标签和元数据。
