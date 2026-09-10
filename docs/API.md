# V1.0 API 清单

统一前缀为 `/api/v1`。除登录外，接口通过 `Authorization: Bearer <token>` 鉴权。

## 统一格式

成功：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

分页：

```json
{
  "code": 0,
  "message": "success",
  "data": { "items": [], "total": 0, "page": 1, "page_size": 20 }
}
```

失败：

```json
{
  "code": 40901,
  "message": "schedule conflict",
  "data": { "conflicts": [] }
}
```

## 认证与首页

| Method | Path | 说明 |
|---|---|---|
| POST | `/auth/login` | 用户名密码登录，返回 JWT 与当前用户 |
| GET | `/auth/me` | 当前用户、角色和权限 |
| POST | `/auth/logout` | 前端退出流程的服务端确认 |
| GET | `/dashboard/summary` | 可见项目、延期任务、待确认预约和今日安排摘要 |
| GET | `/lookups/users` | 已登录用户可用的最小用户选项，不包含邮箱、电话和角色 |
| GET | `/lookups/departments` | 已登录用户可用的有效部门选项 |

登录请求：

```json
{ "username": "admin", "password": "ChangeMe123!" }
```

## 用户、组织与 RBAC

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET | `/users` | `user:view` | 用户分页；支持 `keyword`、`department_id`、`status` |
| POST | `/users` | `user:edit` | 新增用户并可分配角色 |
| GET | `/users/{id}` | `user:view` | 用户详情 |
| PUT | `/users/{id}` | `user:edit` | 编辑、启停或重置密码 |
| PUT | `/users/{id}/roles` | `role:edit` | 替换用户角色 |
| GET | `/departments` | `organization:view` | 部门列表 |
| POST | `/departments` | `organization:edit` | 新增部门 |
| PUT | `/departments/{id}` | `organization:edit` | 编辑部门 |
| GET | `/organizations/tree` | `organization:view` | 组织树，可按 `department_id` 过滤 |
| POST | `/organizations` | `organization:edit` | 新增 L1-L4 节点 |
| PUT | `/organizations/{id}` | `organization:edit` | 编辑节点并校验层级循环 |
| GET | `/roles` | `role:view` | 默认角色与当前权限 |
| GET | `/permissions` | `role:view` | 权限列表 |
| PUT | `/roles/{id}/permissions` | `role:edit` | 替换角色权限 |

## 项目与成员

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET | `/projects` | `project:view` | 项目分页与数据范围过滤 |
| POST | `/projects` | `project:edit` | 新建项目 |
| GET | `/projects/{id}` | `project:view` | 项目详情 |
| PUT | `/projects/{id}` | `project:edit` | 编辑项目 |
| DELETE | `/projects/{id}` | `project:edit` | 仅逻辑删除草稿项目 |
| GET | `/projects/{id}/members` | `project:view` | 当前有效成员 |
| POST | `/projects/{id}/members` | `project:edit` | 添加或重新启用成员 |
| DELETE | `/projects/{id}/members/{user_id}` | `project:edit` | 写入 `left_at`，保留历史 |

## 任务

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET | `/tasks` | `task:view` | 分页；支持项目、负责人、状态过滤 |
| POST | `/tasks` | `task:edit` | 新增一级或二级任务 |
| GET | `/tasks/{id}` | `task:view` | 任务详情与动态 `effective_status` |
| PUT | `/tasks/{id}` | `task:edit` | 编辑任务并校验父子循环 |
| GET | `/tasks/{id}/evaluation` | `process_report:view` | 当前有效评价 |
| PUT | `/tasks/{id}/evaluation` | `evaluation:edit` | 新增或覆盖任务评价 |

## 人力预约

| Method | Path | 权限/主体 | 说明 |
|---|---|---|---|
| GET | `/schedules` | `schedule:view` | 看板列表；支持日期、项目、人员、部门、状态过滤 |
| POST | `/schedules` | `schedule:edit` | 创建草稿，保存前检查冲突 |
| GET | `/schedules/{id}` | `schedule:view` | 预约详情 |
| PUT | `/schedules/{id}` | `schedule:edit` | 编辑；已确认记录变为 `changed` |
| DELETE | `/schedules/{id}` | `schedule:edit` | 仅删除 `draft` 或 `cancelled` |
| POST | `/schedules/{id}/submit` | `schedule:edit` | `draft/rejected → pending` |
| POST | `/schedules/{id}/confirm` | 预约本人或授权管理者 | `pending/changed → confirmed` |
| POST | `/schedules/{id}/reject` | 预约本人或授权管理者 | `pending/changed → rejected` |

确认和拒绝请求：

```json
{ "reason": "可选说明；拒绝时前端要求填写" }
```

冲突返回 HTTP 409：

```json
{
  "code": 40901,
  "message": "schedule conflict",
  "data": {
    "conflicts": [
      {
        "schedule_id": 1,
        "project_id": 10,
        "project_name": "项目A",
        "task_id": 20,
        "task_name": "任务1",
        "user_id": 1001,
        "user_name": "张三",
        "start_time": "2026-10-01T09:00:00",
        "end_time": "2026-10-01T12:00:00"
      }
    ]
  }
}
```

## 执行、报表与日志

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| GET | `/executions` | `execution:view` | 执行记录；`mine=true` 仅看本人 |
| POST | `/executions` | `execution:edit` | 填写执行记录 |
| GET | `/executions/{id}` | `execution:view` | 执行详情 |
| PUT | `/executions/{id}` | `execution:edit` | 修改执行记录 |
| GET | `/reports/process` | `process_report:view` | 项目过程聚合报表 |
| GET | `/reports/workload` | `process_report:view` | `confirmed/running` 日负载 |
| GET | `/operation-logs` | `operation_log:view` | 日志分页和修改前后数据 |

## 主要业务错误码

| HTTP | Code | 场景 |
|---|---:|---|
| 400 | 40001 | 时间、状态、层级或业务参数不合法 |
| 401 | 40101 | 登录失败、Token 无效/过期、账号禁用 |
| 403 | 40301 | 权限不足或超出项目数据范围 |
| 404 | 40401 | 资源不存在 |
| 409 | 40901 | 人力排期冲突 |
| 409 | 40902 | 用户名重复 |
| 409 | 40921 | 项目编号重复 |
| 422 | 42201 | Pydantic 请求校验失败 |
| 500 | 50001 | 数据库操作失败，响应不暴露堆栈 |
