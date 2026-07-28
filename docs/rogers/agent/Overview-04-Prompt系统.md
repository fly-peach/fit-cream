# Prompt 系统

## 渐进式三层设计

系统提示词采用渐进式注入设计，分为三层，每层由不同的机制注入：

```
→ Base Layer：身份、能力、规则、约束、示例
→ Intent Layer：根据检测到的意图动态注入
→ Context Layer：用户具体数据和近期记忆
```

### 第一层：基础层

始终存在的固定内容，由 `SYSTEM_PROMPT` 常量定义，包含六个部分：

1. **身份定义**：名为"小健"的 AI 健身教练，FitCream 专属
2. **能力说明**：所有 17 个工具的 Markdown 表格 + 多模态能力说明
3. **核心规则**：10 条行为准则（工具使用、安全保障、交互原则）
4. **输出格式**：语言风格要求、结构化输出规范、响应组织方式
5. **约束边界**：不得提供医疗建议、不得推荐极端饮食、不得处理非健身内容
6. **行为示例**：6 种典型对话流程的模式化展示

### 第二层：意图层

由 IntentMiddleware 在运行时动态注入。根据检测到的意图，系统追加对应的 `SystemMessage`。每个意图消息包含：

- 用户意图理解指导
- 工具选择建议
- 执行流程规范
- 质量要求

目前定义的 9 个意图提示词：plan_creation、checkin、stats_analysis、exercise_query、image_analysis、memory_operation、profile_update、general_chat、knowledge_query。

### 第三层：上下文层

通过 `build_system_prompt()` 函数动态构建，作为用户消息之前的系统消息注入。包含：

- **当前日期**：ISO 格式
- **用户称呼**：user.name
- **用户目标**：映射为中文（lose_fat→减脂、gain_muscle→增肌、maintain→维持体型、improve_health→改善健康）
- **用户数据**：身高、体重、BMI（含分类：偏瘦/正常/偏胖/肥胖）
- **近期活跃**：连续打卡天数（来自 CheckinService.get_streak）
- **活跃计划**：当前有效的训练计划名称和周数（来自 PlanService.list_plans）
- **额外上下文**：预留的扩展字段
- **记忆上下文**：来自 MemoryPipeline.get_memory_context()，包含三段历史信息

## 记忆上下文格式

`get_memory_context()` 从三种记忆中检索并格式化为结构化文本，注入到系统提示词：

```
# 记忆上下文

## 相关经历
- [日期] 用户完成了[事件]...

## 用户信息
- [主体] [谓词] [客体]

## 可用技能
- [技能名称]: [描述]
```

## 集成机制

System Prompt 的完整形态在每次对话开始时动态组装：
1. Base Layer 作为 agent 构造时的 `system_prompt` 参数
2. Context Layer 通过 `_build_user_context()` 生成，作为 `system` 角色消息注入 `messages` 数组
3. Intent Layer 由 IntentMiddleware 在 after_model 钩子中追加 `SystemMessage`

这种分层设计允许 Base Layer 在编译时固定，Context Layer 在请求时动态，Intent Layer 在运行时按需调整。
