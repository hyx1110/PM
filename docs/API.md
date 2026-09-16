# V2.0 API 清单

业务接口统一使用 `/api/v1` 前缀；登录外的接口通过 `Authorization: Bearer <token>` 鉴权。普通 JSON 响应保持：

```json
{ "code": 0, "message": "success", "data": {} }
```

Excel 下载直接返回 `.xlsx` 文件流，不使用 JSON 包装。

登录请求统一使用员工号/登录账号：

```json
{
  "employee_no": "E10001",
  "password": "ChangeMe123!"
}
```

## 认证、首页与查找项

| Method | Path | 权限/主体 | 说明 |
|---|---|---|---|
| POST | `/auth/login` | 公开 | 登录并返回 JWT |
| GET | `/auth/me` | 已登录 | 当前用户、角色、权限 |
| POST | `/auth/logout` | 已登录 | 退出确认 |
| GET | `/dashboard/summary` | 已登录 | V2 驾驶舱摘要与 14 日趋势 |
| GET | `/lookups/users` | 已登录 | 最小用户选项 |
| GET | `/lookups/schedule-users` | 已登录 | 支持项目/姓名/工号/部门/组织筛选；PM 返回本人/项目组、L3 返回全量、L4 返回本人/直属及第二级下属、普通成员返回本人 |
| GET | `/lookups/departments` | 已登录 | 有效部门选项 |

## 用户、组织与 RBAC

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET/POST | `/users` | `user:view` / `user:edit` | 查询/新增用户 |
| GET/PUT/DELETE | `/users/{id}` | `user:view` / `user:edit` | 用户详情/更新/软删除 |
| PUT | `/users/{id}/roles` | `role:edit` | 替换用户的系统角色；空列表会自动恢复项目成员角色 |
| GET/POST | `/departments` | `organization:view/edit` | 部门列表/新增 |
| PUT/DELETE | `/departments/{id}` | `organization:edit` | 更新/删除无组织节点的部门 |
| GET | `/organizations/tree` | 已登录 | L1-L4 组织树，用于部门→组织→人员级联选择 |
| POST/PUT/DELETE | `/organizations`、`/organizations/{id}` | `organization:edit` | 新增/更新/删除叶子组织节点 |
| GET | `/roles`、`/permissions` | `role:view` | 角色和权限 |
| PUT | `/roles/{id}/permissions` | `role:edit` | 替换角色权限 |

新增用户的 `department_id`、`password` 和 `confirm_password` 必填。`employee_no` 同时作为唯一登录账号，长度为 2–50，只接受可见 ASCII 字符，必须至少包含一个英文字母或数字，且不能包含空格；`name` 姓名字段不受该字符集限制。用户列表支持部门和组织筛选。用户 DELETE 为软删除，活动业务未移交时返回 `40904`。

新增用户示例：

```json
{
  "employee_no": "E10001",
  "password": "ChangeMe123!",
  "confirm_password": "ChangeMe123!",
  "name": "张三",
  "email": "zhangsan@example.com",
  "department_id": 10,
  "organization_id": 100,
  "supervisor_id": 8,
  "role_ids": [5]
}
```

其中 `password` 必须与 `confirm_password` 一致。用户业务字段只包含员工号/登录账号、姓名、邮箱、部门、组织、直属主管和系统角色；未选择任何角色时默认授予 `project_member`。

## 项目、任务、执行与评价

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET/POST | `/projects` | `project:view` / 项目经理 | 所有人可查询全部项目；仅项目经理可创建，`code` 自动生成，必须传至少一名 `member_ids` |
| POST | `/projects/{id}/submit` | 项目创建人 | 项目经理提交给直属主管；兼具 L3/超级管理员角色时自动通过 |
| GET/PUT/DELETE | `/projects/{id}` | `project:view/edit` | 详情/更新/草稿逻辑删除 |
| POST | `/projects/{id}/approve` | `approver_id` 对应的直属主管 | 批准项目和初始工时额度 |
| POST | `/projects/{id}/reject` | `approver_id` 对应的直属主管 | 驳回项目，必须填写 `note` |
| GET/POST | `/projects/{id}/hour-requests` | `project:edit` 且可管理该项目 / 项目负责人 | 查询/提交追加工时申请 |
| GET | `/projects/hour-requests/pending` | 当前 L3 | 首页查询本人作为部门 L3 的待审批追加工时 |
| POST | `/projects/{id}/hour-requests/{request_id}/approve` | 所属部门当前 L3 | 批准追加工时并累加额度 |
| POST | `/projects/{id}/hour-requests/{request_id}/reject` | 所属部门当前 L3 | 驳回追加工时，必须填写 `note` |
| GET/POST | `/projects/{id}/members` | `project:view/edit` | 成员列表/加入 |
| DELETE | `/projects/{id}/members/{user_id}` | `project:edit` | 保留历史地移除普通成员；项目经理固定成员不可移除 |
| GET/POST | `/tasks` | `task:view/edit` | 所有人可查看；项目经理为本人项目新增任务，`owner_ids` 支持多人负责人 |
| GET | `/tasks/mine` | `task:view` | 只返回当前用户负责的“我的任务” |
| GET/PUT/DELETE | `/tasks/{id}` | `task:view/edit` | 所有人可看详情；只有任务负责人可更新或受限软删除 |
| GET/POST | `/executions` | `execution:view/edit` | 执行记录列表/新增 |
| GET/PUT/DELETE | `/executions/{id}` | `execution:view/edit` | 执行详情；只有记录本人可更新或软删除 |
| GET/PUT | `/tasks/{id}/evaluation` | `process_report:view` / L3 | 仅 L3 且项目已结束、任务已完成时可评价 |

项目创建必须传入 `department_id` 和大于 0 的 `budget_hours`，`manager_id` 必须是当前项目经理本人；项目编号不由客户端传入。项目经理先得到 `draft`，提交时需要有效 `supervisor_id`；创建人兼具 L3 时可自动通过。追加工时审批人仍是项目所属部门 L3。

项目列表支持 `department_id/organization_id/employee_no/name`，任务列表支持同名四类人员筛选；组织、工号和姓名按当前有效项目成员或任务负责人匹配。任务的 `owner_ids` 是完整负责人集合，旧字段 `owner_id` 仅作为兼容主负责人保留。

系统角色显示名已经更新为 L3/L4，但鉴权代码继续使用 `department_manager`/`functional_manager`，避免破坏已有 Token、用户角色和接口判断。

## 排期看板

| Method | Path | 权限/主体 | 说明 |
|---|---|---|---|
| GET | `/schedules` | `schedule:view` | 按日期、项目、人员、部门、状态查询，`sort_order=asc|desc` 控制时间顺序 |
| GET | `/schedules/my-pending` | 当前登录用户 | 首页快捷查询预约到本人且待本人确认的记录 |
| POST | `/schedules` | 项目经理 | 仅可使用本人负责且已审批的项目预约有效成员；直接提交为 `pending` |
| POST | `/schedules/batch` | 项目经理 | 对全部目标执行相同范围校验，原子提交且每人分别审批 |
| POST | `/schedules/copy-week` | 原提交人 | 逐条重新校验当前项目成员和预约范围，无效项跳过 |
| GET/PUT/DELETE | `/schedules/{id}` | 可见用户 / 原提交人 | 详情/编辑/取消并保留历史 |
| POST | `/schedules/{id}/move` | `schedule:edit` | 拖动改期，校验 `expected_version` |
| POST | `/schedules/{id}/submit` | 原提交人 | 仅用于升级前遗留草稿，不是新预约流程 |
| POST | `/schedules/{id}/withdraw` | 原提交人/当前项目经理 | 对方确认前撤回预约并释放额度 |
| POST | `/schedules/{id}/confirm` | 被预约人本人 | 本人确认，管理员和各级经理不能代批 |
| POST | `/schedules/{id}/reject` | 被预约人本人 | 本人拒绝，必须填写原因 |
| GET | `/personal-time-blocks` | `schedule:view` | 查询看板范围内的个人时间安排，支持日期、人员、状态和排序筛选 |
| GET | `/personal-time-blocks/mine` | 当前登录用户 | 分页查询本人的生效/已撤回个人安排 |
| POST | `/personal-time-blocks` | 当前登录用户 | 为本人创建培训、会议、休假、外出、出差或其他时间安排 |
| POST | `/personal-time-blocks/{id}/withdraw` | 安排创建人本人 | 撤回个人安排并释放时段 |
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

所有预约对象都必须存在 `project_members.left_at IS NULL` 的成员关系，且当前用户必须是所选项目负责人并具有项目经理角色。该规则在新建、编辑、遗留草稿提交、拖动、批量创建和复制周入口统一执行。

个人时间创建示例：

```json
{
  "time_type": "leave",
  "start_time": "2026-10-12T13:00:00",
  "end_time": "2026-10-12T17:30:00",
  "remark": "下午休假"
}
```

`time_type` 支持 `training`、`meeting`、`leave`、`out_of_office`、`business_trip`、`other`。个人安排只能创建给当前登录用户，也只能由本人撤回；生效中的所有个人安排都会阻止领导或项目经理在重叠时段创建、修改、确认、拖动、批量创建或复制项目预约。个人安排与已有有效项目预约重叠时同样拒绝创建。

驾驶舱的“待我确认的人力预约”仅统计和展示当前登录用户作为被预约人的 `pending/changed` 记录，支持在驾驶舱内直接确认或填写原因拒绝。共享看板的时间文本显示在刻度线上，格子表示两个刻度间的 30 分钟区间。正常工作时间保持白色；工作日上班前、午休、下班后和普通周末使用灰色禁用背景；工作日历明确标记的法定节假日使用红色系背景；调休工作日仍开放正常工作时段。

点击共享看板人员姓名时，前端使用 `user_id`、`sort_order=desc` 单独查询该人员的全部预约，不携带当前看板日期或项目筛选，并通过 `page/page_size` 分页。后端人员范围为：项目经理的自己项目组、L3 全量、L4 的直属与第二级下属、普通成员本人；一旦人员可见，就返回其跨项目时间占用。

项目和任务列表对所有已授权用户可见；项目编辑与成员维护只允许本项目经理，任务编辑只允许任务负责人，执行记录写操作只允许记录本人。日程查看继续使用人员关系范围。

时间冲突返回 `40901` 和 `data.conflicts`；其中 `conflict_type=project_booking|personal_time` 用于区分项目预约和个人安排。版本冲突返回 `40903` 和 `data.current_version`。

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
| DELETE | `/notifications/{id}` | `notification:view` | 软删除本人单条通知；未读通知同时转为已读 |
| DELETE | `/notifications/read` | `notification:view` | 软删除本人全部已读通知 |
| GET/PUT | `/notifications/preferences` | `notification:view` | 本人渠道和临期时间设置 |

外部渠道由 Celery 任务异步投递；未配置渠道不会阻塞业务请求。

## 报表与数据交换

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET | `/reports/process` | `process_report:view` | 项目过程报表 |
| GET | `/reports/workload` | `process_report:view` | 日人员负载 |
| GET | `/reports/workload-summary` | `analytics:view`（兼容权限码） | 隐藏 UI 使用的日/周/月人员负载后台汇总 |
| GET | `/data-exchange/templates/{users|projects|tasks}` | `import:manage` | 标准导入模板 |
| POST | `/data-exchange/imports/{users|projects|tasks}` | `import:manage` | 上传 `.xlsx` 并逐行导入 |
| GET | `/data-exchange/imports` | `import:manage` | 导入任务与错误明细 |
| GET | `/data-exchange/exports/schedules` | `export:download` | 排期 Excel |
| GET | `/data-exchange/exports/executions` | `export:download` | 执行 Excel |
| GET | `/data-exchange/exports/process-report` | `export:download` | 过程报表 Excel |
| GET | `/operation-logs` | `operation_log:view` | 操作审计 |

三类导出和负载接口要求 `start_date`、`end_date`；负载汇总额外支持 `granularity=day|week|month`。负载、风险和工作日历接口保留供后台使用，当前前端不展示对应页面。
日负载与负载汇总的 `available_hours` 统一读取工作日历：法定节假日为 0，调休工作日按 `STANDARD_WORK_HOURS` 计入；已完成预约保留在历史负载统计中，已拒绝、已撤回和已取消预约不计入。

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
| 409 | 40905 | `position_id` 已分配给其他员工 |
| 409 | 40923 | 项目已有待审批的追加工时申请 |
| 409 | 40913/40914 | 部门仍有组织节点/组织仍有子节点 |
| 409 | 40931/40932 | 任务仍有子任务或业务记录 |
| 422 | 42201 | 请求模型校验失败 |
| 500 | 50001 | 服务端或数据库错误，响应不暴露堆栈 |
