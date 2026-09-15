# V2.0 数据库说明

## 关系概览

```text
users n ── n roles ── n permissions
departments 1 ── n organizations 1 ── n users
users 1 ── 1 employee_profiles
users n ── 1 users              via supervisor_id

projects n ── n users          via project_members
projects n ── 1 users          via approver_id（提交时锁定的直属主管）
projects 1 ── n tasks          tasks 支持两级自关联
projects 1 ── n project_hour_requests
users/projects/tasks 1 ── n schedule_bookings
users 1 ── n personal_time_blocks
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
| `users` | 增加 `is_deleted`、`employee_no`，手机号长度扩展至 60 | 用户采用软删除；员工号是登录账号，内部 `id` 继续作为数字主键 |
| `departments` / `organizations` | 增加 `data_source` | 区分本地测试数据与 HRDB 同步数据；HRDB 来源只读 |
| `employee_profiles` | 新表并增加 `data_source` | 一对一正式人员档案、唯一岗位编号、独立人事管理职级与数据来源 |
| `user_roles` | 增加 `is_manual`、`is_hr_auto` | 分别标记人工系统授权和人事职级自动授权，两个来源可同时存在 |
| `schedule_bookings` | 增加 `version`、`source_booking_id` | 拖动乐观锁；复制周来源追溯 |
| `risk_records` | 增加 `fingerprint`、标题、来源 JSON、检测/到期/解决时间 | 指纹唯一去重，风险处理闭环 |
| `notifications` | 新表并增加 `is_deleted` | 收件人、事件、关联对象、渠道、已读状态和软删除标记 |
| `notification_preferences` | 新表 | `user_id` 唯一，站内/邮件/企业微信/钉钉与提醒小时 |
| `import_jobs` | 新表 | 文件名、对象、总计/成功/失败、最多 500 条错误 JSON、操作人 |
| `projects` | 增加 `budget_hours`、审批状态/创建人/直属审批人字段 | 普通项目经理提交给直属主管；L3/超级管理员创建自动通过；额度控制预约总工时 |
| `project_hour_requests` | 新表 | 项目经理追加工时申请、L3 审批结果与意见 |
| `work_calendar_days` | 新表 | `holiday/workday` 日期覆盖；迁移内置 2026 法定安排 |
| `personal_time_blocks` | 新表 | 用户本人的培训/会议/休假/出差/其他占用，支持生效与撤回状态 |
| `tasks` | 增加 `is_deleted` 并统一状态 | 业务删除保留历史；状态为未开始、进行中、已完成、已暂停、已取消，延期为动态展示状态 |
| `execution_records` | 增加 `is_deleted` | 删除后不参与正常查询和统计，但保留审计历史 |

V1 业务表和历史字段均保留；`users`、`projects`、`schedule_bookings` 只做向后兼容的增量扩展，其余部门、组织、成员、任务、执行、评价和日志结构不删除原字段。

## 数据约定

- 工时、百分比使用 `DECIMAL`；导出时转换为 Excel 数字单元格。
- 业务时间使用无时区 `DATETIME`，部署环境统一配置 `Asia/Shanghai`。
- 状态/类型继续使用字符串，枚举由 Schema 和 Service 校验。
- 风险 `fingerprint` 对自动扫描生成的同一业务事件保持稳定；V1 预留记录允许为空。
- 通知正文和导入错误属于业务数据，数据库备份与访问控制应覆盖这些表。
- 外部渠道密码和 Webhook 只存在环境变量中，不写数据库或操作日志。
- `users.id` 继续作为内部数字主键；`employee_no` 是登录员工号，兼容字段 `username` 通过检查约束与其保持相同。用户软删除时设置 `is_deleted=1`、禁用账号并从业务查询中隐藏；原员工号保留，避免历史身份与新账号混淆。
- `users.department_id`、`organization_id`、`supervisor_id` 直接表示正式口径中的部门、组织和直属上级关系。当前仅建立 MySQL 测试架构，不导入真实人员数据。
- `employee_profiles.user_id` 唯一保证一人一份档案，`position_id` 唯一保证同一岗位编号不能同时属于多名员工。
- `employee_profiles.hr_management_level` 与系统角色分离：`department_manager` 自动授予系统 L3，`management_manager` 自动授予系统 L4，`employee` 无自动管理角色。
- `user_roles.is_manual/is_hr_auto` 可以同时为真。人事职级改变只清理旧的自动来源；如果人工来源仍存在，角色关联不会删除。
- 数据库检查约束限制人事管理职级只能取三种约定值，并保证每条 `user_roles` 至少存在人工或职级自动来源之一。
- 每个有效用户至少拥有一个系统角色；没有显式角色的升级数据和新用户默认获得 `project_member`。
- `data_source=hrdb` 的人员档案、部门和组织由正式 HRDB 同步，项目管理系统拒绝人工修改或删除；本地测试数据仍可维护。
- 普通项目经理提交项目时将当时有效的 `supervisor_id` 写入 `projects.approver_id`，后续仅该直属主管可批准或驳回；L3 和超级管理员创建项目时直接批准。追加工时仍由项目所属部门 L3 审批。
- 项目创建时必须同时写入至少一名普通成员；项目经理以 `project_role=manager` 写入 `project_members` 并作为不可移除的固定成员，所有任务负责人和预约对象统一校验当前有效成员关系。
- 任务持久化状态限定为 `not_started/running/completed/suspended/cancelled`；`delayed` 仅根据计划结束时间动态计算，不再作为数据库状态保存。
- 预约工时由服务端按照半小时时段计算，客户端提交的 `planned_hours` 不作为可信数据。
- 项目已占用工时统计 `pending/confirmed/changed/running/completed`；`rejected/withdrawn/cancelled` 不占额度。
- 工作日历有记录时以 `day_type` 为准，无记录时周一至周五为工作日、周六日为非工作日；预约校验、驾驶舱周容量和日/周/月负载报表共用该口径。
- 软删除的项目、任务和执行记录不参与正常列表及经营统计，物理记录和关联历史仍保留供审计追溯。
- 个人时间类型为 `training/meeting/leave/out_of_office/business_trip/other`，状态为 `active/withdrawn`；只有 `active` 记录参与预约冲突检测。

## 索引与约束

- `risk_records.fingerprint` 唯一索引用于扫描幂等。
- 通知按 `recipient_id`、`status`、`event_type`、`related_id` 查询。
- 导入任务按 `resource_type`、`status`、`operator_id` 查询。
- `notification_preferences.user_id` 唯一。
- 排期保留 `ix_schedule_user_range` 冲突索引，并新增复制来源索引。
- 项目审批状态、创建人/审批人、追加工时项目/状态/申请人和工作日历日期均有索引。
- 个人时间按用户、开始、结束和状态建立组合索引，用于重叠时段查询。
- `users.employee_no` 唯一并建立查询索引；另有 `employee_no = username` 检查约束，保证登录兼容字段不分叉。
- `employee_profiles.user_id`、`position_id` 均唯一并建立索引；人事管理职级单独建立索引。
- 部门、组织和人员档案的数据来源，以及任务、执行记录和通知的软删除字段均建立查询索引。
- `projects.approver_id` 建立外键与索引，直属主管被删除时置空，历史审批结果仍保留。

## 事务策略

- 普通写操作由 Service 统一提交。
- Excel 导入的每个数据行使用保存点：单行失败不回滚其他成功行；汇总结果与错误明细和导入业务数据在同一外层事务提交。
- 批量预约先锁定项目额度，再检查所有目标人员冲突和整批总工时；任一人员冲突或总额度不足则不创建整批记录。
- 复制周排期允许部分成功，但每条冲突都会进入 `skipped` 返回结果。
- 项目预约与个人时间创建均锁定目标用户记录后再做双向冲突检查，避免并发请求同时占用同一用户时段。
- 人员档案与职级自动角色在同一个用户写事务内更新；人工角色替换只改变 `is_manual`，不会覆盖 `is_hr_auto`。
- 风险、排期和导入关键动作写入 `operation_logs`。

## 迁移顺序

```text
20260909_0001  V1.0 全量基线
      ↓
20260910_0002  V2.0 风险/通知/导入/排期历史增量
      ↓
20260911_0003  用户软删除字段与索引
      ↓
20260911_0004  项目审批基础、工时额度、追加申请、工作日历与 L3/L4 名称
      ↓
20260912_0005  个人时间安排与预约冲突拦截数据表
      ↓
20260914_0006  员工号、人员档案、人工/职级自动角色来源
      ↓
20260914_0007  HRDB 只读来源、直属主管审批、任务状态、业务软删除与默认成员角色
      ↓
20260915_0008  为历史项目回填项目经理固定成员关系
```

维护者执行：

```powershell
cd backend
alembic upgrade head
python -m scripts.init_data
```

`20260915_0008` 是数据回填迁移，降级时不会自动删除已补齐的项目经理成员记录，以免误删原本就存在的合法成员关系。继续降级 `0007` 会删除 HRDB 来源标记、直属审批人及任务/执行/通知软删除字段，但不会自动恢复被规范化的旧任务状态，也不会撤销迁移时补授的项目成员角色；执行前必须备份。
