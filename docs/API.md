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
| GET/PUT | `/users/{id}` | `user:view` / `user:edit` | 用户详情/更新 |
| PUT | `/users/{id}/roles` | `role:edit` | 替换用户角色 |
| GET/POST | `/departments` | `organization:view/edit` | 部门列表/新增 |
| PUT | `/departments/{id}` | `organization:edit` | 更新部门 |
| GET | `/organizations/tree` | `organization:view` | L1-L4 组织树 |
| POST/PUT | `/organizations`、`/organizations/{id}` | `organization:edit` | 新增/更新组织节点 |
| GET | `/roles`、`/permissions` | `role:view` | 角色和权限 |
| PUT | `/roles/{id}/permissions` | `role:edit` | 替换角色权限 |

## 项目、任务、执行与评价

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET/POST | `/projects` | `project:view/edit` | 项目列表/新增 |
| GET/PUT/DELETE | `/projects/{id}` | `project:view/edit` | 详情/更新/草稿逻辑删除 |
| GET/POST | `/projects/{id}/members` | `project:view/edit` | 成员列表/加入 |
| DELETE | `/projects/{id}/members/{user_id}` | `project:edit` | 保留历史地移除成员 |
| GET/POST | `/tasks` | `task:view/edit` | 两级任务列表/新增 |
| GET/PUT | `/tasks/{id}` | `task:view/edit` | 任务详情/更新 |
| GET/POST | `/executions` | `execution:view/edit` | 执行记录列表/新增 |
| GET/PUT | `/executions/{id}` | `execution:view/edit` | 执行详情/更新 |
| GET/PUT | `/tasks/{id}/evaluation` | `process_report:view` / `evaluation:edit` | 达成评价 |

## 排期看板

| Method | Path | 权限/主体 | 说明 |
|---|---|---|---|
| GET | `/schedules` | `schedule:view` | 按日期、项目、人员、部门、状态查询 |
| POST | `/schedules` | `schedule:edit` | 创建草稿 |
| POST | `/schedules/batch` | `schedule:edit` | 为多位人员原子创建排期草稿 |
| POST | `/schedules/copy-week` | `schedule:edit` | 复制来源周，冲突项跳过并返回明细 |
| GET/PUT/DELETE | `/schedules/{id}` | `schedule:view/edit` | 详情/编辑/删除草稿 |
| POST | `/schedules/{id}/move` | `schedule:edit` | 拖动改期，校验 `expected_version` |
| POST | `/schedules/{id}/submit` | `schedule:edit` | 提交确认 |
| POST | `/schedules/{id}/confirm` | 本人或授权经理 | 确认 |
| POST | `/schedules/{id}/reject` | 本人或授权经理 | 拒绝 |

批量排期：

```json
{
  "user_ids": [101, 102],
  "project_id": 10,
  "task_id": 20,
  "start_time": "2026-10-01T09:00:00",
  "end_time": "2026-10-01T17:00:00",
  "remark": "现场支持"
}
```

拖动改期：

```json
{
  "start_time": "2026-10-02T09:00:00",
  "end_time": "2026-10-02T17:00:00",
  "expected_version": 3
}
```

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
| 422 | 42201 | 请求模型校验失败 |
| 500 | 50001 | 服务端或数据库错误，响应不暴露堆栈 |

