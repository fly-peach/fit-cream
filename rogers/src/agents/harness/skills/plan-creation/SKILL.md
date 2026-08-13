---
name: plan-creation
description: 用户大规模设计/调整训练或饮食计划时使用，引导「先规划再执行」的 plan-execute 流程
---

# Plan Creation Skill

本技能引导你完成「会话识别 -> 信息补全 -> 计划设计 -> 提案展示 -> 审批后执行」的完整 plan-execute 流程。
适用于用户想要**创建新计划**或**大幅调整现有计划**的场景（训练计划或饮食计划）。

## 何时使用

- 用户说「帮我设计/制定一个 XX 计划」（减脂/增肌/饮食/训练）
- 用户要求根据当前数据重新规划训练或饮食
- 用户明确要调整计划的总体结构（换目标、改天数、换分化），而非单点修改

**不适用**：单点微调（如「加个动作」「把周三改成休息日」「删掉卧推」）直接用 add/update/remove 系列工具，无需走完整流程。

## 流程

### 1. 确认进入长流程并建立待办队列
明确告知用户接下来会先收集信息、再出提案、确认后才落库，避免用户误以为已创建。
随即**第一步**就调用 `present_plan_queue_tool` 建立覆盖全流程的闭环待办清单（见第 4 节），
此后沿清单逐项做、做了打勾。

### 2. Intake 信息收集（表单化，作为待办项在对话内完成）

> 以下为信息收集的**表单机制**（form_id/落库分流/安全研判），具体执行节奏由待办队列驱动：
> 每个收集维度对应一个待办项（5.1），标 in_progress -> 弹表单 -> 提交后打勾。

先调用 `get_user_summary_tool` 读取后端已有数据与 `missing_fields`，然后按以下原则收集：

**原则一：有数据就不打扰。** 后端档案已有的字段（身高/体重/年龄/性别/目标等）直接复用，
不要询问、不要弹表单让用户修改。

**原则二：缺失的可落库字段用 `body_profile` 表单补全。**
当 `missing_fields` 非空时，调用 `present_form_tool(form_id="body_profile")`，
并把已知字段放入 `fields` 预填（前端渲染为只读）。用户提交后消息以
「[表单提交: body_profile]」回到对话，读取其中**新补充的字段**，调用
`update_user_profile_tool` 写入档案，再重新调 `get_user_summary_tool` 确认。

**原则三：规划参考维度逐卡收集（不落库）。** 科学安全的计划需要多维度数据，
按**必须 / 可选 / 不需要**取舍后，对以下维度调用 `present_form_tool`（每次一张卡，可连续多张）：

**必须收集（安全底线与定强度依据）：**

| form_id | 维度 | 内容 |
|---|---|---|
| health_safety | 🏥 健康与安全基线 | 既往病史、伤病限制、用药、过敏史、孕期、PAR-Q 风险、医生建议（**不可跳过**） |
| fitness_level | 💪 当前体能水平 | 心肺耐力、力量水平、训练经验、柔韧性、体脂率 |
| exercise_history | 🏃 运动经历与习惯 | 每周频率（定计划密度）、单次时长、偏好类型、过往成果 |
| lifestyle | 💡 生活方式与客观环境 | 职业作息、饮食、睡眠、压力、可用器械、偏好时段 |

**按需可选：**

| form_id | 维度 | 内容 |
|---|---|---|
| diet_profile | 🍽 饮食偏好与结构 | 饮食偏好、忌口/过敏、烹饪条件、每日餐次、外食比例、预算（设计饮食计划时收集） |
| baseline | 📏 基线评测数据 | 力量参考动作、身体围度（用于定强度与后续复测追踪） |

**不需要：** 目标与动机、补剂。目标已由 body_profile 覆盖，动机与补剂对计划设计无决定性作用，不单独收集。

用户在对话中已主动提供的信息直接采纳，对应表单字段传入 `fields` 预填，不要重复问。
信息充足的维度可跳过对应表单，但 `health_safety` 不可跳过。

### 3. 表单提交后的数据分流（重要）

用户提交表单后，消息以「[表单提交: <form_id>]」结构化文本回到对话：

- 标注「写入档案」的字段（仅 body_profile）-> 调用 `update_user_profile_tool` 落库
- 标注「仅本次参考」的字段（其余各维度表单）-> **只用于本次计划设计，禁止调用任何工具写入数据库**

### 3.5 用药与安全风险评估（重要）

设计训练/饮食计划前，必须结合 health_safety 的字段做安全研判，逐项触发对应约束：

| 触发条件 | 安全约束 |
|---|---|
| medication 非「无」 | 评估药物对运动/饮食的交互影响；抗凝/降压/降糖/精神类等药物需保守控制强度，避免高冲击与极限负荷；必要时建议先咨询医生 |
| 慢性病史（medical_history 有高血压/心脏病/糖尿病等） | 控制强度与心率，避免 Valsalva 屏气发力；饮食注意钠/糖/血糖波动 |
| 伤病/身体限制（injuries 非空） | 规避刺激伤处的动作，改用替代动作；急性期仅做无痛范围练习 |
| PAR-Q 高风险（parq_result=high） | **先建议咨询医生**，不直接设计高强度计划；若 low/uncertain 则按常规设计 |
| allergies / 食物不耐 | 饮食计划**必须排除**对应致敏原/不耐受食物，并在方案中注明替换 |
| pregnancy 非空 | 女性孕期/产后以低强度、安全为原则，避免压迫腹部与高风险动作，饮食按孕期需求调整，必要时建议遵医嘱 |

### 3.6 分层设计规则（按经验水平）

根据 `training_experience` / `strength_level` 分层设计，避免所有用户输出同一模板：

- **beginner / never（初学者）**：低容量低强度起步，动作选择以基础复合动作为主，强调动作模式与渐进，组数 2-3 组、次数 10-15 次，给足恢复与学习空间。
- **intermediate（进阶）**：中等容量，可引入分化与渐进超负荷，组数 3-4 组，次数按目标（力量 3-6 次 / 增肌 8-12 次）。
- **advanced（资深）**：较高容量与强度，可细化分化、周期安排与技术变化，组数 4-5 组，次数按周期目标。

**约束降级**（无论经验层级，一旦命中即降级处理）：
- 器械受限（equipment 无杠铃/器械）-> 用哑铃/自重/弹力带替代动作，不硬套自由重量计划
- 伤病/身体限制 -> 按 3.5 规避伤处动作
- 时间受限（weekly_frequency 低 / session_duration 短）-> 压缩到 2-3 次/周、单次 30-45 分钟的高效计划
- PAR-Q 高风险 -> 按 3.5 先咨询医生

### 4. 第一步：创建闭环待办队列（核心）

收到计划设计意图后，**第一件事**就调用 `present_plan_queue_tool` 创建一份覆盖「从信息收集到计划落库」的**完整闭环待办清单**。待办面板只显示 todo（标题+状态），不含别的内容；所有表单与当日方案都在对话消息流内渲染。

初始清单（信息收集项数视用户档案已有数据裁剪，已有则直接打勾跳过；每个 todo 可带可选 `description` 短说明，如「填写伤病与安全基线」）：

```
title: "<目标>计划设计"
todos:
  - intake-body:       收集基础身体数据
  - intake-health:     收集健康与安全基线
  - intake-fitness:     收集当前体能水平
  - intake-history:     收集运动经历与习惯
  - intake-lifestyle:   收集生活方式与客观环境
  - analyze:            分析信息并确定训练类型
  - outline:            生成训练大纲
  - assemble:           装配完整计划提案
  - approve:            审批并落库
```

> 逐日设计 todo（如 `design-day-1`...）在大纲确认后由 `present_plan_queue_tool` **重组清单**插入 `outline` 与 `assemble` 之间（见 5.3）。

**用户移除待办**：用户可点面板删除按钮，收到「`[移除待办: <id>]`」结构化消息时，从队列中移除该 todo（或标 `skipped`），并用 `present_plan_queue_tool` 重渲染更新后的清单。若移除的是必选 intake 项，需补问一句是否真的不需要该项信息。

### 5. 逐项执行：做了就打勾

对清单中每个 pending 项，**一步一步做**：

1. `update_plan_queue_item_tool(item_id, status="in_progress", queue=全量更新后的快照)` 标记进行中
2. 执行该步（见 5.1/5.2/5.3）
3. 完成后 `update_plan_queue_item_tool(item_id, status="completed", queue=全量快照)` 打勾
4. 进入下一个 pending 项

**重要**：`update_plan_queue_item_tool` 的 `queue` 入参必须是**更新后的完整队列快照**（含全部 todo 最新状态）。QueueMiddleware 每轮会注入当前快照，复制后翻转对应项 status 即可。

#### 5.1 信息收集项（表单在对话内完成）

- 标记该项 in_progress -> 调 `present_form_tool(form_id=...)` 在对话内弹表单
- 用户提交（「[表单提交: ...]」）后：body_profile 字段调 `update_user_profile_tool` 落库，其余维度仅本次参考
- 调 `get_user_summary_tool` 复核 -> 该项打勾 completed
- 档案已有数据的维度直接打勾跳过，不打扰用户

#### 5.2 分析项（确定训练类型）

- 综合信息确定 training_type（决定全程强度/容量基调）：
  - goal=gain_muscle -> `muscle_gain`
  - goal=lose_fat -> 体型正常/偏瘦或明确「先减后增」倾向 `recomp`；否则 `fat_loss`
  - goal=improve_health/maintain -> 询问「有氧为主/力量为主/均衡？」；只要跑步骑车 -> `cardio_only`
  - 歧义时**主动询问**：「这阶段主要想减脂、增肌、还是先减脂再增肌？」
- v1：`recomp` 暂按单阶段处理。完成后打勾 analyze

#### 5.3 大纲项（生成大纲 + 重组清单）

- 按 3.6 分层规则产出训练日大纲（分化策略 + 每日 focus + day_type）
- **重组清单**：再次调用 `present_plan_queue_tool(title, todos)`，把逐日设计 todo
  （`design-day-1`「周一 · 胸部+三头」...）插入 `outline` 与 `assemble` 之间
- 询问用户确认大纲（可调整分化/频率/训练日）-> 确认后打勾 outline

#### 5.4 逐日设计项（对话内当日方案卡）

对每个 `design-day-N`，**一日一轮**（禁止批量设计多日）：

1. update 标记 in_progress
2. `get_exercises_tool(muscle_group=..., equipment=..., difficulty=..., semantic_query=...)` 检索候选
   （伤病场景用语义检索，如「不刺激膝盖的腿部动作」）
3. 按 3.6 分层 + 3.5 安全约束挑动作设计组次/重量/休息，给 `rationale`；
   用户指定或库无匹配用 `custom_name` 自定义动作
4. `present_day_design_tool(item_id, day_design, rationale)` 在对话内渲染当日方案卡
   （动作表格 + 设计依据 + 确认按钮）
5. 用户点确认 -> 收到「`[确认当日设计: <item_id>]`」-> update 打勾 completed -> 下一日
6. 用户要调整 -> 按反馈重新设计当日，再次 `present_day_design_tool`（同 item_id）

#### 5.5 装配项

- 汇总各日 `day_design` 为完整计划：
  1. `present_plan_tool(title, description, content=完整表格, changes=[...])`
     （content 含各训练日动作/组次/重量表格 + 经验层级说明；changes 覆盖会落库的全部变更）
  2. **紧接着** `create_plan_tool`，**必须传入 `days`**（各日 `day_design` 装配的 `PlanDayCreate`），
     后端直接落库、不再模板重新生成 -> 提案与落库一致。**禁止**不传 `days` 走后端模板路径
- **`changes` 变更总览必须逐项覆盖本次将写入数据库的全部变更**（这是用户审批的决策依据）：
  - 至少包含：计划主体（新增训练计划 + 目标/难度/天数/周期）、各训练日（新增训练日 + 分化 focus）、
    各动作（新增动作 + 组次/重量）、以及同步更新的用户档案字段（如体重）。
  - 一项一行为宜，`detail` 写清具体内容（如「每周4天力量训练」「卧推 4组×8次 60kg」）。
  - 宁可多列，不可漏列——漏列会导致用户在批准时看不到真实将要发生的变更。
- 打勾 assemble

#### 5.6 审批落库项

- `create_plan_tool`（传 days）触发 HITL 中断，前端弹审批卡片：
  - **approve**：落库（计划状态=active）-> 打勾 approve -> 总结要点，流程结束
  - **reject（无修改）**：询问调整方向，**回到对应日重新走 5.4 当日设计**，再装配提案
  - **reject（带修改稿）**：按修订稿重设计对应部分 -> 重新 present_plan_tool + create
  - 每次 reject 后必须重新走完整「提案+审批」，不得直接落库

### 6. 饮食计划（直接提案，不走待办队列）

饮食计划暂不走待办队列：基于 intake（含 `diet_profile`）设计后直接
`present_plan_tool` + `create_diet_plan_tool` 触发审批（沿用原有流程）。

**预览==落库约束**：装配饮食计划时，`present_plan_tool` 的 `content` 必须按
`days` 结构书写，并在调用 `create_diet_plan_tool` 时**传入 `days`**
（`DietDayCreate` 列表：`day_of_week`/`focus`/`meals[{meal_type, food_name, calories,
protein_g, carbs_g, fat_g, portion}]`）。提供 `days` 后后端直接落库，不再用模板重新
生成，保证提案与落库一致。**禁止**不传 `days` 走后端模板路径（模板生成的餐食与提案
展示的餐食不一致，用户批准的是另一份计划）。`changes` 需逐项覆盖计划主体与每日餐食。

## 循环与收尾规则（重要）

整个计划设计流程是一个**多轮推进循环**，沿待办清单一步一步做、做了打勾，直到审批落库才结束。每轮回复必须推进到下一个交互点，禁止开放式收尾。

**每轮必须结束于以下状态之一：**
1. **表单待填**：已调用 `present_form_tool` 等待用户提交信息（intake 项）
2. **大纲待确认**：已 `present_plan_queue_tool` 重组清单插入逐日 todo，等待用户确认大纲
3. **当日方案待确认**：已调用 `present_day_design_tool` 等待用户确认当日设计（逐日项）
4. **计划待审批**：已调用 `present_plan_tool` + `create_plan_tool`/`create_diet_plan_tool` 触发 HITL 中断

**禁止的收尾方式：**
- 禁止以开放式文案收尾，如「需要时告诉我」「还有什么想问的吗」「随时找我」
- 禁止在未到审批就停止并等待用户主动开口
- 禁止调用创建工具之前跳过 `present_plan_tool` 提案展示
- 禁止在单轮内批量设计多日（逐日循环须一日一轮，等用户确认当日后再进入次日）

**拒绝后的处理：**
- 用户 reject（无修改）：主动询问调整方向；训练计划回到对应日重新走 5.4 当日设计，再装配提案
- 用户 reject（带修改稿）：按修订稿重新设计对应部分 -> `present_plan_tool` + `create_plan_tool`
- 每次 reject 后必须重新走完整的「提案 + 审批」流程，不得直接落库

**唯一结束条件：** 审批通过（approve）-> 落库 -> 打勾 approve 项 -> 总结要点后流程结束。

## 审批边界（execute 前需用户确认的部分）

以下工具在执行前会**强制中断等待用户审批**，无需你额外询问：

| 工具 | 是否中断 | 触发场景 | 审批时用户看到 |
|---|---|---|---|
| `create_plan_tool` | 中断 | 创建/替换训练计划 | 计划提案卡片 + 变更清单 |
| `create_diet_plan_tool` | 中断 | 创建/替换饮食计划 | 计划提案卡片 + 变更清单 |
| `delete_plan_tool` | 中断 | 归档现有计划 | 待归档计划概览 |
| `remove_plan_day_tool` | 中断 | 删除训练日 | 待删除训练日 |
| `remove_exercise_tool` | 中断 | 删除动作 | 待删除动作 |
| `sync_plan_day_tool` | 中断 | 同步训练日（覆盖目标日动作） | 源日/目标日概览 |

其余编辑类工具（`update_plan_tool` / `add_plan_day_tool` / `add_exercise_tool` / `update_exercise_tool`）不中断，直接执行；编辑/删除动作前先用 `get_plan_detail_tool` 获取 `plan_day_id` / `exercise_id`。

## 注意事项

- **第一步就建待办**：收到设计意图后立即 `present_plan_queue_tool` 建闭环清单，再逐项做；不要先收集完信息才建队列
- **待办面板只写 todo**：面板只渲染标题+状态，不要把表单内容/当日方案表格塞进 todos；表单走 `present_form_tool`、当日方案走 `present_day_design_tool`，都在对话消息流内渲染
- **做了就打勾**：每完成一项立即 `update_plan_queue_item_tool(status="completed", queue=全量快照)`；开始做就标 in_progress
- 提案的 `content` 表格与 `changes` 变更清单务必完整可读，这是用户审批决策的依据
- 不要在调用 `present_plan_tool` 之前就调用 `create_plan_tool`，否则用户看不到提案
- 调用 `present_form_tool` / `present_plan_tool` / `present_plan_queue_tool` / `present_day_design_tool` 后等待用户响应，不要在同一轮继续调用创建工具之外的其他工具
- `present_day_design_tool` 与 `update_plan_queue_item_tool` 配合：展示方案后等用户确认，确认消息收到后再调 update 打勾；一日一轮，勿批量
- 审批通过后**不要**再次请求用户输入，直接总结执行结果
- 若用户在 intake 阶段已提供足够信息，不要重复询问
- 若采集了 baseline 基线数据，可在计划总结中建议用户按周期（如 4 周）复测力量/围度，用于下一步调整依据（本期仅文案引导，不落库）
