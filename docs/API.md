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
| PUT | `/auth/me` | 已登录 | 修改本人姓名和邮箱 |
| PUT | `/auth/me/password` | 已登录 | 校验当前密码后修改本人登录密码 |
| POST | `/auth/logout` | 已登录 | 退出确认 |
| GET | `/dashboard/summary` | 已登录 | V2 驾驶舱摘要与 14 日趋势 |
| GET | `/lookups/users` | 已登录 | 最小用户选项 |
| GET | `/lookups/schedule-users` | 已登录 | `keyword` 同时匹配姓名/工号，并支持项目/部门/组织筛选；PM 返回本人/项目组、L3/超管返回全量、L4 返回本人及全部层级下属、普通成员返回本人 |
| GET | `/lookups/schedule-projects` | 已登录 | 返回当前日程人员范围中出现的项目；本人负责项目即使尚无排期也保留，供共享看板筛选 |
| GET | `/lookups/l3-users` | 已登录 | 仅返回具有 L3 系统角色的有效用户，供部门负责人选择 |
| GET | `/lookups/departments` | 已登录 | 有效部门选项 |

## 用户、组织与 RBAC

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET/POST | `/users` | `user:view` / `user:edit` | 查询/新增用户 |
| GET/PUT/DELETE | `/users/{id}` | `user:view` / `user:edit` | 用户详情/更新/软删除 |
| PUT | `/users/{id}/roles` | `role:edit` | 替换用户的系统角色；空列表会自动恢复项目成员角色 |
| GET/POST | `/departments` | `organization:view/edit` | 部门列表/新增 |
| PUT/DELETE | `/departments/{id}` | `organization:edit` | 更新/删除无组织节点的部门 |
| GET | `/organizations/tree` | 已登录 | L1-L4 组织树，每个节点包含其直属用户；前端另列未分配组织人员 |
| POST/PUT/DELETE | `/organizations`、`/organizations/{id}` | `organization:edit` | 新增/更新/删除叶子组织节点 |
| GET | `/roles`、`/permissions` | `role:view` | 角色和权限 |
| PUT | `/roles/{id}/permissions` | `role:edit` | 替换角色权限 |

新增用户的 `department_id`、`supervisor_id`、`password` 和 `confirm_password` 必填；最高级主管由维护者直接写入数据库，不在新增用户表单中创建。`employee_no` 同时作为唯一登录账号，长度为 2–50，只接受可见 ASCII 字符，必须至少包含一个英文字母或数字，且不能包含空格；`name` 姓名字段不受该字符集限制。用户列表支持姓名/工号及部门/组织合并筛选。用户 DELETE 为软删除，活动业务、直属下属或管理关系未移交时返回 `40904`。

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

`super_admin` 只允许初始化脚本创建。用户新增、用户编辑、角色分配和 Excel 导入都不能把超级管理员角色授予其他账号；既有初始化管理员仍受“至少保留一个有效超级管理员”保护。

## 项目、任务、执行与评价

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET/POST | `/projects` | `project:view/edit` | GET 按全局角色、管理链条及本人负责/参与关系返回；POST 自动生成 `code`，创建者须为项目经理/L4/L3/超管并传至少一名 `member_ids` |
| GET | `/projects/approvals/pending` | 当前审批人 | 独立返回本人待审批项目，不扩大常规项目列表 |
| POST | `/projects/{id}/submit` | 项目创建人 | 项目经理提交给直属主管；兼具 L3/超级管理员角色时自动通过 |
| GET/PUT/DELETE | `/projects/{id}` | `project:view/edit` | 详情/更新/草稿逻辑删除 |
| POST | `/projects/{id}/complete` | 项目负责人/L3/超管 | 所有未取消任务完成且无待办依赖后，手动确认项目完成 |
| POST | `/projects/{id}/approve` | `approver_id` 对应的直属主管 | 批准项目和初始工时额度 |
| POST | `/projects/{id}/reject` | `approver_id` 对应的直属主管 | 驳回项目，必须填写 `note` |
| GET/POST | `/projects/{id}/hour-requests` | `project:edit` 且可管理该项目 / 项目负责人 | 查询/提交追加工时申请 |
| GET | `/projects/hour-requests/pending` | 当前 L3 | 首页查询本人作为部门 L3 的待审批追加工时 |
| POST | `/projects/{id}/hour-requests/{request_id}/approve` | 所属部门当前 L3 | 批准追加工时并累加额度 |
| POST | `/projects/{id}/hour-requests/{request_id}/reject` | 所属部门当前 L3 | 驳回追加工时，必须填写 `note` |
| GET/POST | `/projects/{id}/members` | `project:view/edit` | 成员列表/加入 |
| DELETE | `/projects/{id}/members/{user_id}` | `project:edit` | 保留历史地移除普通成员；项目经理固定成员不可移除 |
| GET/POST | `/tasks` | `task:view/edit` | GET 按可见项目返回；项目负责人/L3/超管为可管理项目新增任务，`owner_ids` 支持多人负责人 |
| GET | `/tasks/mine` | `task:view` | 只返回当前用户负责的“我的任务” |
| GET/PUT/DELETE | `/tasks/{id}` | `task:view/edit` | 任务负责人查看和维护；项目经理可在本项目支持场景读取详情 |
| GET/POST | `/executions` | `execution:view/edit` | 普通用户查询/新增本人记录；超管/L3 可查看全部并为有效任务负责人填报 |
| GET/PUT/DELETE | `/executions/{id}` | `execution:view/edit` | 记录本人可更新或软删除，超级管理员/L3 可全局维护 |
| GET/PUT | `/tasks/{id}/evaluation` | `process_report:view` / `evaluation:edit` | 本项目负责人、L3 或超管在项目已结束且任务已完成后一次性评价 |

项目创建必须传入 `department_id` 和大于 0 的 `budget_hours`；非全局角色的 `manager_id` 必须是当前创建人本人，且负责人须具备项目经理、L4、L3 或超管角色。项目编号不由客户端传入。普通创建人先得到 `draft`，提交时需要有效 `supervisor_id`；L3/超管创建时自动通过。追加工时审批人仍是项目所属部门 L3。

项目列表支持 `department_id/organization_id/employee_no/name`，任务列表支持同名四类人员筛选；组织、工号和姓名按当前有效项目成员或任务负责人匹配。任务的 `owner_ids` 是完整负责人集合，旧字段 `owner_id` 仅作为兼容主负责人保留。

任务列表默认依次按计划开始日期、计划结束日期、创建时间和任务 ID 倒序返回；任务管理树中的同级任务沿用该顺序。

任务计划起止日期和执行实际起止日期都使用 `YYYY-MM-DD`，结束日期不得早于开始日期，实际日期不能晚于当前北京时间日期。执行记录不传 `actual_hours` 时按日期范围内的工作日容量自动计算；显式传值必须大于 0 且不得超过该容量。任务状态取最新一条未删除执行记录，删除最新记录后回退到上一条，父任务自动汇总；项目运行态随任务变化，但全部任务完成不会自动把项目设为完成，必须调用 `POST /projects/{id}/complete`。任务管理只能手工取消，不能直接改为进行中或已完成。“已延期”基于计划结束日期实时计算。项目产生评价后，执行记录进入只读状态。

系统角色显示名已经更新为 L3/L4，但鉴权代码继续使用 `department_manager`/`functional_manager`，避免破坏已有 Token、用户角色和接口判断。

## 排期看板

| Method | Path | 权限/主体 | 说明 |
|---|---|---|---|
| GET | `/schedules` | `schedule:view` | 按日期、项目、人员、部门、状态查询，`sort_order=asc|desc` 控制时间顺序 |
| GET | `/schedules/my-pending` | 当前登录用户 | 首页快捷查询预约到本人且待本人确认的记录 |
| POST | `/schedules` | `schedule:edit` | 项目负责人使用本人已审批项目预约有效成员；L3/超管可全局管理。预约本人自动确认，其他预约为 `pending`；已经开始或过去的时段直接返回明确业务错误 |
| POST | `/schedules/batch` | `schedule:edit` | 对全部目标执行相同范围校验并原子提交；本人项自动确认，其他人员分别审批 |
| POST | `/schedules/copy-week` | 原提交人 | 逐条重新校验当前项目成员和预约范围，无效项跳过 |
| GET/PUT/DELETE | `/schedules/{id}` | 可见用户 / 原提交人 | 详情/编辑/取消并保留历史 |
| POST | `/schedules/{id}/move` | `schedule:edit` | 拖动改期，校验 `expected_version` |
| POST | `/schedules/{id}/submit` | 原提交人 | 仅用于升级前遗留草稿，不是新预约流程 |
| POST | `/schedules/{id}/withdraw` | 原提交人/当前项目经理 | 对方确认前撤回预约并释放额度 |
| POST | `/schedules/{id}/confirm` | 被预约人本人 | 一般预约由本人确认；项目负责人预约自己时创建即自动确认，无需调用该接口 |
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

共享看板中带 `⋮⋮` 标识的预约可以按住预约条中间拖动。日/周视图可拖到同一人员行的其他 30 分钟工作时段；月视图可拖到其他工作日，并保留原开始时刻。拖动只改变时间，不用于更换预约人员。允许改期的状态为 `pending`、`changed`、`rejected`、`confirmed`；普通提交人只能移动自己提交的预约，L3 和超级管理员可按其全局日程权限移动。冲突、过期、跨人员及乐观锁版本变化都会返回明确原因。

`planned_hours` 即使传入也不会被信任，服务端按开始/结束时间重新计算。一次预约必须同一天、按 30 分钟选择，并完整落在 `08:30-12:00` 或 `13:00-17:30` 内；工作日历中的节假日和普通周末不可预约，开始时间必须晚于当前北京时间。待确认预约在提交时即占用项目工时额度，额度不足返回业务错误并提示先申请追加工时。

待确认或变更待确认的预约若直到预约结束仍未获得本人确认，生命周期同步会将其标记为 `cancelled`，保存“预约结束前未完成确认”的取消原因，并向预约发起人和被预约人发送站内通知。共享看板历史列表和详情会展示该原因，不再静默取消。

所有预约对象都必须存在 `project_members.left_at IS NULL` 的成员关系；普通操作者必须是所选项目负责人，L3/超管可全局管理。该规则在新建、编辑、遗留草稿提交、拖动、批量创建和复制周入口统一执行。

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

点击共享看板人员姓名时，前端使用 `user_id`、`sort_order=desc` 单独查询该人员的全部预约，不携带当前看板日期或项目筛选，并通过 `page/page_size` 分页。后端人员范围为：项目经理的自己项目组、L3/超管全量、L4 的本人及全部层级下属、普通成员本人；一旦人员可见，就返回其跨项目时间占用。

项目和任务列表统一按权限范围过滤：L3/超管全量，L4 为本人及全部下属相关数据，项目经理和项目成员为本人负责、参与或承担任务的数据；成员身份只读，项目负责人及全局角色可维护。执行记录默认只返回本人，超级管理员/L3 可查看和维护全部。日程查看使用 L3/超管全员、L4 全部下属、项目经理项目成员、普通成员本人的人员关系范围。

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

通知偏好功能已移除。临期阈值统一读取 `NOTIFICATION_UPCOMING_HOURS`；外部渠道由环境变量统一启用并由 Celery 异步投递。未配置渠道不会阻塞业务请求，站内通知始终保存。

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
| GET | `/operation-logs` | `operation_log:view` | 操作审计，返回操作者和字段级 `change_summary` |

三类导出和负载接口要求 `start_date`、`end_date`；负载汇总额外支持 `granularity=day|week|month`。负载、风险和工作日历接口保留供后台使用，当前前端不展示对应页面。
日负载与负载汇总的 `available_hours` 统一读取工作日历：法定节假日为 0，调休工作日按 `STANDARD_WORK_HOURS` 计入；已完成预约保留在历史负载统计中，已拒绝、已撤回和已取消预约不计入。

应用日志使用北京时间并实时写入 `logs/YYYY-MM-DD/app-HH.log`，跨整点自动切换到新的小时文件；数据库操作日志与文件日志同时保留。

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
| 409 | 40905 | 用户仍承担管理关系或活动业务，不能停用 |
| 409 | 40906–40909 | 用户部门或系统角色仍被未结束项目、部门负责人关系占用 |
| 409 | 40923 | 项目已有待审批的追加工时申请 |
| 409 | 40913/40914 | 部门仍有组织节点/组织仍有子节点 |
| 409 | 40931–40936 | 任务仍有子任务、活动预约或执行记录等依赖 |
| 422 | 42201 | 请求模型校验失败 |
| 500 | 50001 | 服务端或数据库错误，响应不暴露堆栈 |
