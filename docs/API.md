# V2.0 API 清单

业务接口统一使用 `/api/v1` 前缀；登录外的接口通过 `Authorization: Bearer <token>` 鉴权。普通 JSON 响应保持：

```json
{ "code": 0, "message": "success", "data": {} }
```

Excel 下载直接返回 `.xlsx` 文件流，不使用 JSON 包装。

## 认证、首页与查找项

| Method | Path | 权限/主体 | 说明 |
|---|---|---|---|
| POST | `/auth/login` | 公开 | 登录并返回 JWT |
| GET | `/auth/me` | 已登录 | 当前用户、角色、权限 |
| POST | `/auth/logout` | 已登录 | 退出确认 |
| GET | `/dashboard/summary` | 已登录 | V2 驾驶舱摘要与 14 日趋势 |
| GET | `/lookups/users` | 已登录 | 最小用户选项 |
| GET | `/lookups/departments` | 已登录 | 有效部门选项 |

## 用户、组织与 RBAC

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET/POST | `/users` | `user:view` / `user:edit` | 查询/新增用户 |
| GET/PUT/DELETE | `/users/{id}` | `user:view` / `user:edit` | 用户详情/更新/软删除 |
| PUT | `/users/{id}/roles` | `role:edit` | 替换用户角色 |
| GET/POST | `/departments` | `organization:view/edit` | 部门列表/新增 |
| PUT/DELETE | `/departments/{id}` | `organization:edit` | 更新/删除无组织节点的部门 |
| GET | `/organizations/tree` | `organization:view` | L1-L4 组织树 |
| POST/PUT/DELETE | `/organizations`、`/organizations/{id}` | `organization:edit` | 新增/更新/删除叶子组织节点 |
| GET | `/roles`、`/permissions` | `role:view` | 角色和权限 |
| PUT | `/roles/{id}/permissions` | `role:edit` | 替换角色权限 |

新增用户的 `username` 长度为 2–50，只接受可见 ASCII 字符，必须至少包含一个英文字母或数字，且不能包含空格；`name` 姓名字段不受该字符集限制。用户 DELETE 为软删除，活动业务未移交时返回 `40904`。

## 项目、任务、执行与评价

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET/POST | `/projects` | `project:view` / 项目经理本人 | 项目列表/提交项目和初始工时额度给 L3 审批 |
| GET/PUT/DELETE | `/projects/{id}` | `project:view/edit` | 详情/更新/草稿逻辑删除 |
| POST | `/projects/{id}/approve` | 所属部门当前 L3 | 批准项目和初始工时额度 |
| POST | `/projects/{id}/reject` | 所属部门当前 L3 | 驳回项目，必须填写 `note` |
| GET/POST | `/projects/{id}/hour-requests` | 可见项目用户 / 项目经理 | 查询/提交追加工时申请 |
| POST | `/projects/{id}/hour-requests/{request_id}/approve` | 所属部门当前 L3 | 批准追加工时并累加额度 |
| POST | `/projects/{id}/hour-requests/{request_id}/reject` | 所属部门当前 L3 | 驳回追加工时，必须填写 `note` |
| GET/POST | `/projects/{id}/members` | `project:view/edit` | 成员列表/加入 |
| DELETE | `/projects/{id}/members/{user_id}` | `project:edit` | 保留历史地移除成员 |
| GET/POST | `/tasks` | `task:view/edit` | 两级任务列表/新增 |
| GET/PUT/DELETE | `/tasks/{id}` | `task:view/edit` | 任务详情/更新/受限删除 |
| GET/POST | `/executions` | `execution:view/edit` | 执行记录列表/新增 |
| GET/PUT/DELETE | `/executions/{id}` | `execution:view/edit` | 执行详情/更新/删除 |
| GET/PUT | `/tasks/{id}/evaluation` | `process_report:view` / `evaluation:edit` | 达成评价 |

项目创建必须传入 `department_id` 和大于 0 的 `budget_hours`。`manager_id` 必须是当前用户本人，当前用户必须具有 `project_manager` 角色；`status` 即使传入也会在审批前固定为 `Draft`。

角色显示名已经更新为 L3/L4，但鉴权代码继续使用 `department_manager`/`functional_manager`，避免破坏已有 Token、用户角色和接口判断。

## 排期看板

| Method | Path | 权限/主体 | 说明 |
|---|---|---|---|
| GET | `/schedules` | `schedule:view` | 按日期、项目、人员、部门、状态查询 |
| GET | `/schedules/my-pending` | 当前登录用户 | 首页快捷查询预约到本人且待本人确认的记录 |
| POST | `/schedules` | 当前项目经理 | 直接提交预约，状态为 `pending` |
| POST | `/schedules/batch` | 当前项目经理 | 为多位人员原子提交预约，每人分别审批 |
| POST | `/schedules/copy-week` | 当前项目经理 | 复制来源周并直接提交，无效日期/冲突/额度不足项跳过 |
| GET/PUT/DELETE | `/schedules/{id}` | 可见用户 / 原提交人 | 详情/编辑/受限删除 |
| POST | `/schedules/{id}/move` | `schedule:edit` | 拖动改期，校验 `expected_version` |
| POST | `/schedules/{id}/submit` | 原提交人 | 仅用于升级前遗留草稿，不是新预约流程 |
| POST | `/schedules/{id}/withdraw` | 原提交人/当前项目经理 | 对方确认前撤回预约并释放额度 |
| POST | `/schedules/{id}/confirm` | 被预约人本人 | 本人确认，管理员和各级经理不能代批 |
| POST | `/schedules/{id}/reject` | 被预约人本人 | 本人拒绝，必须填写原因 |
| GET | `/work-calendar?year=2026` | `schedule:view` | 查询年度法定节假日/调休覆盖规则 |
| PUT/DELETE | `/work-calendar/{YYYY-MM-DD}` | `calendar:manage` | 新增、修改或删除日期覆盖规则 |

批量排期：

```json
{
  "user_ids": [101, 102],
  "project_id": 10,
  "task_id": 20,
  "start_time": "2026-10-12T08:30:00",
  "end_time": "2026-10-12T11:30:00",
  "remark": "现场支持"
}
```

拖动改期：

```json
{
  "start_time": "2026-10-13T13:00:00",
  "end_time": "2026-10-13T16:30:00",
  "expected_version": 3
}
```

`planned_hours` 即使传入也不会被信任，服务端按开始/结束时间重新计算。一次预约必须同一天、按 30 分钟选择，并完整落在 `08:30-12:00` 或 `13:00-17:30` 内；工作日历中的节假日和普通周末不可预约。待确认预约在提交时即占用项目工时额度，额度不足返回业务错误并提示先申请追加工时。

驾驶舱的“待我确认的人力预约”仅统计和展示当前登录用户作为被预约人的 `pending/changed` 记录，支持在驾驶舱内直接确认或填写原因拒绝。共享看板的时间文本显示在刻度线上，格子表示两个刻度间的 30 分钟区间。正常工作时间保持白色；工作日上班前、午休、下班后和普通周末使用灰色禁用背景；工作日历明确标记的法定节假日使用红色系背景；调休工作日仍开放正常工作时段。

时间冲突返回 `40901` 和 `data.conflicts`；版本冲突返回 `40903` 和 `data.current_version`。

## 风险中心

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET | `/risks` | `risk:view` | 分页及状态、类型、等级、项目、人员筛选 |
| GET | `/risks/stats` | `risk:view` | 按状态和等级汇总 |
| POST | `/risks/sync` | `risk:handle` | 当前数据范围内立即扫描 |
| POST | `/risks/{id}/handle` | `risk:handle` | 置为 `handling/resolved/ignored` 并记录说明 |

处理请求：

```json
{ "status": "resolved", "handling_note": "已调整排期并与成员确认" }
```

## 通知中心

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET | `/notifications` | `notification:view` | 本人通知，支持未读/已读筛选 |
| GET | `/notifications/unread-count` | `notification:view` | 未读数 |
| POST | `/notifications/{id}/read` | `notification:view` | 本人通知已读 |
| POST | `/notifications/read-all` | `notification:view` | 全部已读 |
| DELETE | `/notifications/{id}` | `notification:view` | 删除本人单条通知 |
| DELETE | `/notifications/read` | `notification:view` | 清空本人全部已读通知 |
| GET/PUT | `/notifications/preferences` | `notification:view` | 本人渠道和临期时间设置 |

外部渠道由 Celery 任务异步投递；未配置渠道不会阻塞业务请求。

## 报表与数据交换

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET | `/reports/process` | `process_report:view` | 项目过程报表 |
| GET | `/reports/workload` | `process_report:view` | 日人员负载 |
| GET | `/reports/workload-summary` | `analytics:view` | 日/周/月负载、人员状态、项目占比 |
| GET | `/reports/analytics` | `analytics:view` | 计划实际、延期、成员达成、人力占比 |
| GET | `/data-exchange/templates/{users|projects|tasks}` | `import:manage` | 标准导入模板 |
| POST | `/data-exchange/imports/{users|projects|tasks}` | `import:manage` | 上传 `.xlsx` 并逐行导入 |
| GET | `/data-exchange/imports` | `import:manage` | 导入任务与错误明细 |
| GET | `/data-exchange/exports/schedules` | `export:download` | 排期 Excel |
| GET | `/data-exchange/exports/executions` | `export:download` | 执行 Excel |
| GET | `/data-exchange/exports/process-report` | `export:download` | 过程报表 Excel |
| GET | `/operation-logs` | `operation_log:view` | 操作审计 |

三类导出和两类分析接口都要求 `start_date`、`end_date`；负载汇总额外支持 `granularity=day|week|month`。

## 错误码

| HTTP | Code | 说明 |
|---|---:|---|
| 400 | 40001 | 参数或业务状态不合法 |
| 401 | 40101 | 未登录、Token 失效、账号禁用 |
| 403 | 40301 | 权限不足或超出数据范围 |
| 404 | 40401 | 资源不存在 |
| 409 | 40901 | 排期时间冲突 |
| 409 | 40903 | 排期乐观版本冲突 |
| 409 | 40904 | 用户仍有关联的活动业务，不能删除 |
| 409 | 40923 | 项目已有待审批的追加工时申请 |
| 409 | 40913/40914 | 部门仍有组织节点/组织仍有子节点 |
| 409 | 40931/40932 | 任务仍有子任务或业务记录 |
| 422 | 42201 | 请求模型校验失败 |
| 500 | 50001 | 服务端或数据库错误，响应不暴露堆栈 |
