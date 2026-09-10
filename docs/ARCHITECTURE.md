# V1.0 架构说明

## 总体结构

```text
Browser
  ↓
Nginx
  ├─ /             → Vue 静态文件
  └─ /api、/health → FastAPI
                         ↓
                    SQLAlchemy
                         ↓
                       MySQL 8
```

V1.0 使用同步 SQLAlchemy Session，适合当前三人团队的业务规模和开发复杂度。Redis、消息队列、搜索引擎和异步任务不进入一期。

## 后端职责

| 层级 | 职责 |
|---|---|
| `api/v1` | HTTP Method、Path、Query/Body、鉴权依赖、统一响应包装 |
| `services` | 业务校验、状态机、数据权限、事务、操作日志 |
| `repositories` | SQLAlchemy 查询、分页、聚合、连接查询和冲突查询 |
| `schemas` | 请求校验和响应字段定义 |
| `models` | 表结构、外键、唯一约束和索引 |
| `core` | 环境配置、数据库 Session、JWT、RBAC、异常、日志 |

后端事务由 Service 统一提交。操作日志在嵌套事务中写入，日志写入异常不会回滚已经准备好的主业务变更，但会记录系统错误。

## 前端职责

| 目录 | 职责 |
|---|---|
| `api` | Token 自动携带、统一解包、错误处理和领域接口 |
| `stores` | 当前 Token、用户、角色、权限 |
| `router` | 登录保护、页面权限与懒加载 |
| `types` | 后端字段的静态类型 |
| `components/layout` | 侧栏、顶栏和面包屑 |
| `components/schedule` | 小时表头、人员排期行、预约表单和冲突详情 |
| `views` | 用户、组织、角色、项目、任务、排期、执行、报表、日志页面 |

## 权限与数据范围

系统先检查 RBAC 权限，再在 Service 层检查项目数据范围：

- `super_admin`：所有权限和全部数据。
- `department_manager`、`functional_manager`：本部门项目，以及本人管理或参与的项目。
- `project_manager`：本人管理或参与的项目；只能管理本人负责的项目。
- `project_member`：本人参与的项目；可确认自己的预约、填写自己的执行记录。

前端菜单和按钮权限用于改善体验，后端权限依赖和 Service 数据范围才是安全边界。

## 时间处理

- 数据库字段统一使用 `datetime`，应用与数据库部署时均应设置 `Asia/Shanghai`。
- V1.0 前端统一使用 `YYYY-MM-DD HH:mm:ss` 向 API 传输本地业务时间。
- 排期冲突查询使用 `(user_id, start_time, end_time, status)` 联合索引。
- 周看板显示工作时段 08:00-20:00，日看板显示完整 24 小时；底层预约时间不被视图范围截断。

## 扩展边界

- 二期需要自动风险扫描时，可基于现有 `risk_records` 增加定时任务。
- 二期需要通知时，应订阅预约和风险事件，不把通知逻辑直接写入 Router。
- 二期需要拖拽排期时，复用现有预约 API 与冲突 409 结构，在前端看板组件上增加交互层。
- 外部 MES/EES/YES 接入应建立独立 integration 模块，不直接污染核心业务表。

