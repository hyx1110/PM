# V2.0 数据库说明

## 关系概览

```text
users n ── n roles ── n permissions
departments 1 ── n organizations 1 ── n users

projects n ── n users          via project_members
projects 1 ── n tasks          tasks 支持两级自关联
projects 1 ── n project_hour_requests
users/projects/tasks 1 ── n schedule_bookings
tasks/users 1 ── n execution_records
tasks 1 ── 1 task_evaluations

projects/tasks/users 1 ── n risk_records
users 1 ── n notifications
users 1 ── 1 notification_preferences
users 1 ── n import_jobs
users 1 ── n operation_logs
schedule_bookings 1 ── n schedule_bookings(source_booking_id)
work_calendar_days             法定节假日/调休日期覆盖
```

## V2 新增/扩展

| 表 | 变化 | 关键点 |
|---|---|---|
| `users` | 增加 `is_deleted` | 用户采用软删除，保留历史外键和业务审计数据 |
| `schedule_bookings` | 增加 `version`、`source_booking_id` | 拖动乐观锁；复制周来源追溯 |
| `risk_records` | 增加 `fingerprint`、标题、来源 JSON、检测/到期/解决时间 | 指纹唯一去重，风险处理闭环 |
| `notifications` | 新表 | 收件人、事件、关联对象、渠道、已读状态 |
| `notification_preferences` | 新表 | `user_id` 唯一，站内/邮件/企业微信/钉钉与提醒小时 |
| `import_jobs` | 新表 | 文件名、对象、总计/成功/失败、最多 500 条错误 JSON、操作人 |
| `projects` | 增加 `budget_hours`、审批状态/创建人与审批人字段 | 新项目待 L3 审批；额度控制人力预约总工时 |
| `project_hour_requests` | 新表 | 项目经理追加工时申请、L3 审批结果与意见 |
| `work_calendar_days` | 新表 | `holiday/workday` 日期覆盖；迁移内置 2026 法定安排 |

V1 业务表和历史字段均保留；`users`、`projects`、`schedule_bookings` 只做向后兼容的增量扩展，其余部门、组织、成员、任务、执行、评价和日志结构不删除原字段。

## 数据约定

- 工时、百分比使用 `DECIMAL`；导出时转换为 Excel 数字单元格。
- 业务时间使用无时区 `DATETIME`，部署环境统一配置 `Asia/Shanghai`。
- 状态/类型继续使用字符串，枚举由 Schema 和 Service 校验。
- 风险 `fingerprint` 对自动扫描生成的同一业务事件保持稳定；V1 预留记录允许为空。
- 通知正文和导入错误属于业务数据，数据库备份与访问控制应覆盖这些表。
- 外部渠道密码和 Webhook 只存在环境变量中，不写数据库或操作日志。
- 用户软删除时设置 `is_deleted=1`、禁用账号并从业务查询中隐藏；原用户名保留，避免历史身份与新账号混淆。
- 预约工时由服务端按照半小时时段计算，客户端提交的 `planned_hours` 不作为可信数据。
- 项目已占用工时统计 `pending/confirmed/changed/running/completed`；`rejected/withdrawn/cancelled` 不占额度。
- 工作日历有记录时以 `day_type` 为准，无记录时周一至周五为工作日、周六日为非工作日。

## 索引与约束

- `risk_records.fingerprint` 唯一索引用于扫描幂等。
- 通知按 `recipient_id`、`status`、`event_type`、`related_id` 查询。
- 导入任务按 `resource_type`、`status`、`operator_id` 查询。
- `notification_preferences.user_id` 唯一。
- 排期保留 `ix_schedule_user_range` 冲突索引，并新增复制来源索引。
- 项目审批状态、创建人/审批人、追加工时项目/状态/申请人和工作日历日期均有索引。

## 事务策略

- 普通写操作由 Service 统一提交。
- Excel 导入的每个数据行使用保存点：单行失败不回滚其他成功行；汇总结果与错误明细和导入业务数据在同一外层事务提交。
- 批量预约先锁定项目额度，再检查所有目标人员冲突和整批总工时；任一人员冲突或总额度不足则不创建整批记录。
- 复制周排期允许部分成功，但每条冲突都会进入 `skipped` 返回结果。
- 风险、排期和导入关键动作写入 `operation_logs`。

## 迁移顺序

```text
20260909_0001  V1.0 全量基线
      ↓
20260910_0002  V2.0 风险/通知/导入/排期历史增量
      ↓
20260911_0003  用户软删除字段与索引
      ↓
20260911_0004  项目/L3 审批、工时额度、追加申请、工作日历与 L3/L4 名称
```

维护者执行：

```powershell
cd backend
alembic upgrade head
python -m scripts.init_data
```

降级 `20260911_0004` 会删除项目审批/额度、追加工时申请和工作日历数据，并恢复旧角色显示名；继续降级 `0003`/`0002` 会删除其他增量。执行前必须备份。
