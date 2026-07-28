# fitme Exercise 模型字段增强

**日期**：2026-07-28
**来源**：功能完善 / 对比 fit-cream-last
**详情**：当前 Exercise 表字段较少，缺少分类、细分肌群、热量估算、执行步骤等信息。增强字段以支持更丰富的动作库功能。

## 待办

- [x] Exercise 表新增 category 字段（VARCHAR(50)，索引）
- [x] Exercise 表新增 is_compound 字段（Boolean，默认 False）
- [x] Exercise 表新增 muscle_subgroup 字段（VARCHAR(50)）
- [x] Exercise 表新增 calories_per_min 字段（NUMERIC(6,1)）
- [x] Exercise 表新增 instructions 字段（Text）
- [x] Exercise 表新增 tips 字段（Text）
- [x] ExerciseService 新增 create_exercise 方法（admin）
- [x] ExerciseService 新增 update_exercise 方法（admin）
- [x] ExerciseService 新增 delete_exercise 方法（admin）
- [x] ExerciseService 新增 count 方法（带过滤条件）
- [x] ExerciseService 新增 list_categories 方法
- [x] ExerciseService 新增 list_muscle_groups 方法
- [x] 创建 schemas/exercise.py（ExerciseCreate/ExerciseUpdate/ExerciseOut/ExerciseBrief）
- [x] exercises router 新增 /categories 端点（GET）
- [x] exercises router 新增 /muscle-groups 端点（GET）
- [x] exercises router 新增 POST/PUT/DELETE 端点（admin）
- [x] 创建动作库种子数据脚本
- [ ] 更新 Database-01-训练计划数据表.md 文档
- [ ] 更新 Services-01-Service层.md 文档
- [ ] 更新 Endpoints-03-训练计划.md 文档
