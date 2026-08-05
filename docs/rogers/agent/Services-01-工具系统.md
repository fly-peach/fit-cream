# 工具系统

## 设计原则

所有 Agent 工具使用 LangChain `@tool` 装饰器定义，遵循以下设计原则：

- **同进程直调**：工具直接调用 Service 层方法，不走 HTTP
- **独立会话**：每个工具使用 `async_session_factory()` 创建独立数据库会话
- **RunnableConfig 注入**：从配置中提取 `user_id` 和 `thread_id`
- **结构化返回**：返回带 `success` 标志的 dict

## 工具分组

三组工具在 `create_fitcream_agent()` 中按序加载，任意组加载失败时从略：

### 业务工具

由 `harness/tools/__init__.py` 聚合导出，共 10 个工具：

| 工具 | 功能 | 调用的 Service |
|------|------|---------------|
| list_plans_tool | 列出用户的所有训练计划 | PlanService.list_plans() |
| create_plan_tool | 根据目标创建训练计划 | PlanService.generate_plan_from_goal() |
| create_diet_plan_tool | 创建饮食计划（自动估算热量） | DietPlanService.generate_diet_plan_from_goal() |
| adjust_plan_tool | 调整现有计划 | PlanService.adjust_plan() |
| checkin_tool | 记录训练打卡 | CheckinService.create_checkin() + ExerciseService.search_by_name() |
| get_streak_tool | 查询连续打卡天数 | CheckinService.get_streak() |
| query_stats_tool | 查询训练统计数据 | StatsService（多维度） |
| get_exercises_tool | 搜索动作库 | ExerciseService.search() |
| get_user_profile_tool | 获取用户身体数据 | UserService.get_by_id() |
| update_user_profile_tool | 更新用户个人资料 | UserService.update_profile() |

#### 关键工具逻辑

- **create_plan_tool**：接收 goal、days_per_week、difficulty、preferences。从 User 模型拉取身体数据（身高、体重、年龄、性别），与目标一起传入 PlanService 生成个性化计划
- **create_diet_plan_tool**：接收 goal、target_calories（可选）、preferences。未提供 target_calories 时根据用户体重自动估算：减脂为 weight×22，增肌为 weight×33，维持为 weight×28
- **checkin_tool**：接收用户输入的动作名称列表，通过 ExerciseService.search_by_name() 模糊匹配动作库中的标准动作
- **query_stats_tool**：内置多维度叙事分析（周频次建议、月均情绪、体脂趋势、里程碑识别）

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
