# 项目任务与人力协同管理系统 V1.0

这是一个面向企业内部项目管理和人力协同的前后端分离系统。V1.0 围绕“项目—任务—人员—排期—执行—评价—报表—审计”建立完整业务闭环，用于替代分散的 Excel 排期和人工跟踪方式。

当前仓库已经完成 V1.0 源码、数据库迁移、初始化脚本、部署配置和项目文档的创建。按照项目交付要求，本次仅完成文件创建与编辑，没有安装依赖、执行数据库迁移、运行测试、构建前端或启动任何服务；下文命令由项目维护者自行执行。

## V1.0 功能

- JWT 登录、退出、当前用户与账号禁用控制。
- 用户、部门、L1-L4 组织层级和主管关系维护。
- 超级管理员、部门主管、职能主管、项目经理、项目成员五类默认角色。
- 页面/API 权限与项目数据范围控制。
- 项目、项目成员、投入比例和项目周期维护。
- 一级任务、二级任务、负责人、计划时间、预计工时和动态延期状态。
- 人员 × 日期/小时共享看板，支持日视图和周视图。
- 人力预约草稿、提交、确认、拒绝、修改后重新确认和删除草稿。
- 同一人员有效预约的时间交集检测，冲突时返回 HTTP 409 和全部冲突详情。
- 实际开始、实际结束、实际工时、执行说明和异常原因填报。
- 项目过程报表、预计/实际人力对比、达成率、达成质量和日负载统计。
- 关键业务操作日志和共享看板修改前后数据追溯。

V1.0 不包含 Redis、Kafka、Elasticsearch、Kubernetes、AI 自动排期、AI 风险预测、外部制造系统实时集成、移动 App、复杂审批流、消息中心、Excel 导入导出和拖拽式高级排期。

## 技术栈

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3、TypeScript、Vite、Vue Router、Pinia、Axios、Element Plus、Tailwind CSS、Day.js |
| 后端 | Python 3.11+、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、JWT、bcrypt |
| 数据库 | MySQL 8，字符集 utf8mb4 |
| 部署 | Docker Compose、Nginx、Gunicorn、Uvicorn Worker |

## 目录结构

```text
project_mangement/
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── api/              # 统一请求和领域 API
│   │   ├── components/       # 布局、共享看板组件
│   │   ├── layouts/          # 登录后的主框架
│   │   ├── router/           # 路由与权限守卫
│   │   ├── stores/           # Pinia 登录态
│   │   ├── types/            # TypeScript 领域类型
│   │   └── views/            # V1.0 页面
│   ├── Dockerfile
│   └── README.md
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/           # V1 路由
│   │   ├── core/             # 配置、数据库、安全、异常、权限
│   │   ├── models/           # SQLAlchemy Model
│   │   ├── schemas/          # Pydantic Schema
│   │   ├── repositories/     # 数据访问与聚合查询
│   │   ├── services/         # 业务规则与事务
│   │   └── utils/
│   ├── alembic/              # 数据库迁移
│   ├── scripts/              # 初始角色、权限和管理员
│   ├── tests/                # 可由维护者执行的测试样例
│   ├── Dockerfile
│   └── README.md
├── deploy/nginx/             # Nginx 反向代理配置
├── docs/                     # 架构、API、数据库和范围说明
├── docker-compose.yml
├── .env.example
└── README.md
```

根目录中的原始需求说明、协作指南、设计提示词和 Word 方案均保持原样，作为需求与设计档案。

## 本地准备

建议环境：

- Python 3.11 或更高版本。
- Node.js 20 或更高版本，npm 10 或更高版本。
- MySQL 8.0 或更高版本。
- 可选：Docker Engine 与 Docker Compose V2。

### 1. 创建环境文件

复制后分别修改敏感信息：

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

至少修改 `SECRET_KEY`、`MYSQL_PASSWORD`、`MYSQL_ROOT_PASSWORD` 和 `INITIAL_ADMIN_PASSWORD`。生产环境不要保留示例密码。

### 2. 后端安装与初始化

在 MySQL 中创建数据库后，从 `backend` 目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m scripts.init_data
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`scripts.init_data` 可以重复执行：它会补齐默认权限、角色、角色权限关系和初始管理员，不会重复创建相同记录。初始管理员用户名和密码由 `backend/.env` 中的 `INITIAL_ADMIN_USERNAME` 与 `INITIAL_ADMIN_PASSWORD` 决定。

后端地址：

- 健康检查：`http://localhost:8000/health`
- Swagger：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`

### 3. 前端安装与启动

从 `frontend` 目录执行：

```powershell
npm install
npm run dev
```

开发地址默认为 `http://localhost:5173`。Vite 已将 `/api` 代理到 `http://127.0.0.1:8000`。

### 4. Docker Compose

从根目录执行：

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

Compose 会创建 MySQL 持久卷，等待数据库健康后运行 Alembic、初始化数据并启动后端，再由 Nginx 提供前端和 `/api` 反向代理。默认入口为 `http://localhost`。

## 核心业务规则

### 预约状态机

```text
draft ──提交──> pending ──确认──> confirmed ──执行──> running ──完成──> completed
                    └──拒绝──> rejected ──修改/提交──> pending
confirmed ──修改──> changed ──重新确认──> confirmed
```

- 只有 `draft`、`rejected` 可以自由编辑；`confirmed` 修改后自动成为 `changed`。
- 只有 `draft` 或 `cancelled` 可以删除。
- `pending`、`confirmed`、`changed`、`running` 参与冲突检测。
- `rejected`、`cancelled`、`completed` 不参与冲突检测。
- 冲突公式为 `new_start < existing_end AND new_end > existing_start`；边界刚好相接不冲突。

### 任务延期

查询任务或报表时，如果当前时间已经超过 `planned_end`，且任务状态不是 `completed` 或 `cancelled`，API 会动态返回 `effective_status = delayed`，V1.0 不使用定时任务反复写库。

### 人员负载

人员负载只统计 `confirmed` 和 `running` 预约。默认每日可用工时为 8 小时，可通过 `STANDARD_WORK_HOURS` 修改：

```text
load_rate = planned_hours / available_hours × 100%
load_rate > 100% 时 overloaded = true
```

## API 与响应

所有业务接口使用 `/api/v1` 前缀。成功响应：

```json
{ "code": 0, "message": "success", "data": {} }
```

失败响应：

```json
{ "code": 40001, "message": "error message", "data": null }
```

分页数据位于 `data.items`、`data.total`、`data.page` 和 `data.page_size`。完整接口清单见 [docs/API.md](docs/API.md)。

## 数据库和权限

- 数据库变更必须新增 Alembic revision，不要手工修改生产表结构。
- 用户名和项目编号唯一。
- 项目成员关系保留历史，移除成员写入 `left_at`。
- 项目删除只允许草稿状态，采用 `is_deleted` 逻辑删除。
- 任务父子节点必须属于同一项目，且禁止循环引用。
- 项目经理默认只管理自己的项目；部门主管和职能主管按所属部门获取数据；超级管理员拥有全量数据。
- 账号密码使用 bcrypt 哈希，密码和数据库异常堆栈不会写入业务响应或操作日志。

详情见 [docs/DATABASE.md](docs/DATABASE.md) 与 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 维护者自行验证

本次交付未执行以下命令。维护者完成环境配置后可自行运行：

```powershell
# 后端
cd backend
pytest

# 前端类型检查与构建
cd ../frontend
npm run type-check
npm run build
```

建议按登录、基础数据、项目成员、任务、预约冲突、确认/拒绝、执行填报、报表评价、日志追溯的顺序进行验收。V1.0 范围和验收项见 [docs/V1_SCOPE.md](docs/V1_SCOPE.md)。

