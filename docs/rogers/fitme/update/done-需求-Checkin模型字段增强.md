# fitme Checkin 模型字段增强

**日期**：2026-07-28
**来源**：功能完善 / 对比 fit-cream-last
**详情**：当前 Checkin 表只记录时长、心情、备注，缺少实际强度和估算热量消耗。增强字段以支持更精准的统计。

## 待办

- [x] Checkin 表新增 actual_intensity 字段（VARCHAR(20)）
- [x] Checkin 表新增 calories_burned 字段（Integer）
- [x] CheckinExercise 表新增 notes 字段（Text）
- [x] CheckinExercise 表新增 rpe 字段（Integer）
- [x] 更新 CheckinService 的 create_checkin 方法
- [x] 更新 CheckinService 的 update_checkin 方法
- [x] 更新 CheckinService 的生成热量估算逻辑（结合体重、时长、动作类型）
- [x] 更新 schemas/checkin.py 的 Create/Update/Out
- [ ] 更新 StatsService，使用新增字段做更丰富的统计
- [x] 更新 Agent checkin 工具，支持传入实际强度和 RPE
- [ ] 更新 Database-01-训练计划数据表.md 文档
- [ ] 更新 Services-01-Service层.md 文档
- [ ] 更新 Endpoints-05-打卡与统计.md 文档
