# V1.0 数据库说明

## 关系概览

```text
departments 1 ── n organizations
departments 1 ── n users
organizations 1 ── n users
organizations 1 ── n organizations(parent_id)

users n ── n roles       via user_roles
roles n ── n permissions via role_permissions

projects n ── 1 users(manager)
projects n ── n users via project_members
projects 1 ── n tasks
tasks 1 ── n tasks(parent_id)

users/projects/tasks 1 ── n schedule_bookings
tasks/users 1 ── n execution_records
tasks 1 ── 1 task_evaluations
projects/tasks/users 1 ── n risk_records
users 1 ── n operation_logs
```

## 核心表

| 表 | 用途 | 关键约束或索引 |
|---|---|---|
| `users` | 账号、组织归属、主管、状态 | `username` 唯一，`email` 唯一 |
| `departments` | 部门 | `code` 唯一 |
| `organizations` | L1-L4 组织树 | `(department_id, code)` 唯一，`parent_id` 自关联 |
| `roles` | 系统角色 | `code` 唯一 |
| `permissions` | API/页面权限 | `code` 唯一，`module` 索引 |
| `user_roles` | 用户角色 | `(user_id, role_id)` 唯一 |
| `role_permissions` | 角色权限 | `(role_id, permission_id)` 唯一 |
| `projects` | 项目主数据 | `code` 唯一，经理/部门/状态索引，`is_deleted` 逻辑删除 |
| `project_members` | 成员与投入比例 | `(project_id, user_id)` 唯一，`left_at` 保留历史 |
| `tasks` | 一级/二级任务 | 项目、父任务、负责人、计划结束和状态索引 |
| `schedule_bookings` | 人力预约 | `ix_schedule_user_range` 支撑冲突查询 |
| `execution_records` | 实际执行 | 任务、人员、实际开始和状态索引 |
| `task_evaluations` | 当前任务评价 | `task_id` 唯一，历史由操作日志追溯 |
| `risk_records` | 二期风险闭环预留 | 风险类型、项目、任务、人员、状态索引 |
| `operation_logs` | 关键操作审计 | 操作人、模块、动作、对象和时间索引 |

## 删除策略

- 用户、部门、组织、任务存在业务引用时不提供物理删除接口，使用状态控制。
- 项目只有 `Draft` 可以删除，实际写入 `is_deleted = true`。
- 项目成员移除写入 `left_at`，重新加入时复用关系并清空 `left_at`。
- 排期仅允许物理删除 `draft` 或 `cancelled`，删除前写操作日志。
- 项目物理删除的外键策略已为任务、排期、执行等历史数据设置级联，但应用层默认不执行项目物理删除。

## 字段约定

- 状态和类型均使用字符串，不使用数据库 ENUM，枚举由 Schema 与 Service 校验。
- 主表使用自增整数主键。
- 主表包含 `created_at`、`updated_at`；操作日志只包含不可变的 `created_at`。
- 工时和百分比使用 `DECIMAL`，避免浮点累计误差。
- `before_data`、`after_data` 使用 JSON，日期和 Decimal 写入前转换为 JSON 安全值。

## 迁移

首版 schema：`backend/alembic/versions/20260909_0001_initial_schema.py`。

数据库创建和升级由维护者执行：

```powershell
cd backend
alembic upgrade head
python -m scripts.init_data
```

