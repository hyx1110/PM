# 项目任务与人力协同管理系统 V2.0

面向企业内部项目、任务、人员、排期和执行协同的前后端分离系统。V2.0 在 V1.0 “项目—任务—排期—确认—执行—评价—报表—审计”闭环上，新增管理驾驶舱、人力负载分析、自动风险扫描、风险处理闭环、站内通知、多渠道通知适配、Excel 导入导出、增强排期看板和经营分析报表。

本次交付只创建、编辑和归档源码与文档，没有安装依赖、执行迁移、生成运行时 Excel、运行测试、构建前端或启动任何服务。README 中的命令均留给项目维护者自行执行。

## V2.0 功能范围

V1.0 原有能力全部保留：

- JWT 登录、用户/部门/L1-L4 组织、五类默认角色和项目数据权限。
- 项目、项目成员、两级任务、负责人、周期、预计工时和动态延期状态。
- 日/周人员共享看板，排期草稿、提交、确认、拒绝、变更重确认和冲突检测。
- 执行记录、实际工时、达成评价、项目过程报表和操作日志。

V2.0 新增：

- 管理驾驶舱：项目数量、完成/延期情况、任务完成率、今日排期、待确认排期、风险数量、本周计划工时和 14 日趋势。
- 人员负载分析：日/周/月聚合、人员利用率、空闲/正常/超负载判断、项目人力投入占比。
- 风险中心：排期冲突、负载超限、任务延期、项目延期、任务久未更新的扫描、筛选、处理、解决和忽略闭环。
- Excel 数据交换：用户、项目、任务标准模板和逐行导入；排期、执行、项目过程报表导出；导入任务与错误明细留档。
- 通知中心：新排期、排期变更、确认/拒绝、临期任务和风险通知；支持站内信，预留并实现可配置的邮件、企业微信机器人和钉钉机器人投递器。
- 增强共享看板：日/周/月视图、拖动改期、乐观版本控制、多人员批量排期、复制上周排期、冲突记录跳过。
- 经营分析：计划/实际工时、计划兑现率、项目延期率、任务完成率、成员任务达成和项目内人员投入占比。
- Redis + Celery 后台任务：周期风险扫描、临期提醒生成、多渠道通知投递。

V2.0 不包含 MES/EES/YES 实时集成、AI 自动排期、AI 风险预测、移动 App、复杂审批流和 Kubernetes。这些能力仍属于后续阶段，不在本版本中以占位页面冒充实现。

## 技术栈

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3、TypeScript、Vite、Vue Router、Pinia、Axios、Element Plus、Tailwind CSS、Day.js |
| 后端 | Python 3.11+、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、JWT、bcrypt、openpyxl |
| 数据与任务 | MySQL 8、Redis 7、Celery 5 |
| 部署 | Docker Compose、Nginx、Gunicorn、Uvicorn Worker |

## 目录结构

```text
project_mangement/
├── frontend/
│   └── src/
│       ├── api/                 # 领域 API 与文件下载
│       ├── components/          # 布局、排期看板组件
│       ├── layouts/             # 主框架
│       ├── router/              # 登录与页面权限
│       ├── stores/              # 登录态
│       ├── types/               # TypeScript 领域类型
│       └── views/               # 驾驶舱、风险、负载、通知、报表等页面
├── backend/
│   ├── app/
│   │   ├── api/v1/              # REST API
│   │   ├── core/                # 配置、数据库、安全、权限、异常
│   │   ├── models/              # SQLAlchemy 数据模型
│   │   ├── schemas/             # Pydantic 请求/响应模型
│   │   ├── repositories/        # 查询与聚合
│   │   ├── services/            # 事务和业务规则
│   │   └── tasks/               # Celery 周期任务
│   ├── alembic/versions/        # V1 基线与 V2 增量迁移
│   ├── scripts/init_data.py     # 默认权限、角色、管理员
│   └── tests/                   # 由维护者自行运行的 V1 测试样例
├── deploy/nginx/
├── docs/
├── docker-compose.yml
├── .env.example
├── CHANGELOG.md
└── VERSION
```

根目录中的原始需求说明、协作指南、设计提示词和 Word 方案保持原样，继续作为需求档案。

## 从 V1.0 升级

升级前请备份数据库与环境文件。不要修改或删除 `20260909_0001` 基线迁移；V2.0 通过 `20260910_0002` 增量迁移增加表和字段。

维护者在 `backend` 目录安装新版依赖并执行：

```powershell
pip install -r requirements.txt
alembic upgrade head
python -m scripts.init_data
```

`scripts.init_data` 会幂等补齐 V2 权限，并更新五类系统角色的默认权限集合。详细说明见 [docs/V2_MIGRATION.md](docs/V2_MIGRATION.md)。

## 全新本地部署

### 1. 环境文件

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

至少修改 `SECRET_KEY`、数据库密码、`INITIAL_ADMIN_PASSWORD` 和 `IMPORT_DEFAULT_PASSWORD`。外部通知未配置时，站内通知仍可独立使用。

### 2. 后端、任务队列与数据库

维护者自行准备 MySQL 8 和 Redis 7，然后在 `backend` 目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m scripts.init_data
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

另开终端启动 Celery Worker 和 Beat：

```powershell
celery -A app.tasks.celery_app:celery_app worker --loglevel=INFO
celery -A app.tasks.celery_app:celery_app beat --loglevel=INFO
```

### 3. 前端

在 `frontend` 目录执行：

```powershell
npm install
npm run dev
```

### 4. Docker Compose

根目录执行：

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

Compose 包含 `mysql`、一次性 `migrate`、`redis`、`backend`、`worker`、`beat` 和 `frontend`。`migrate` 成功后其余后端服务才会启动；默认入口为 `http://localhost`。

## V2 配置

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `STANDARD_WORK_HOURS` | `8` | 每工作日可用工时 |
| `RISK_STALE_DAYS` | `7` | 任务久未更新阈值 |
| `IMPORT_MAX_MB` | `10` | Excel 上传上限 |
| `IMPORT_DEFAULT_PASSWORD` | `ChangeMe123!` | 用户导入未填密码时的初始密码，生产必须修改 |
| `REDIS_URL` | `redis://.../0` | Celery Broker/Result Backend |
| `SMTP_*` | 空 | 邮件通知配置 |
| `WECOM_WEBHOOK_URL` | 空 | 企业微信机器人 Webhook |
| `DINGTALK_WEBHOOK_URL` | 空 | 钉钉机器人 Webhook |

## Excel 规则

- 仅接受 `.xlsx`，上传大小受 `IMPORT_MAX_MB` 控制。
- 必须使用系统下载的对应模板，工作表和标题行不能修改。
- 日期必须是 Excel 日期/时间单元格或受支持的标准文本日期；工时必须是数字，不要附加单位。
- 用户、项目、任务分别通过用户名、项目编号及其关联编码解析关系。
- 导入按行使用数据库保存点：合法行成功入库，错误行保留 Excel 行号、字段和原因，最多保留 500 条错误明细。
- 导出工作簿包含筛选、冻结标题、列宽、日期格式和导出说明；日期/数字保留真实单元格类型。

## 风险与通知规则

- 风险扫描既可由风险中心手动触发，也可由 Celery Beat 每两小时执行。
- 同一业务风险使用稳定 `fingerprint` 去重；重复扫描刷新风险内容和检测时间，不重复创建。
- 风险状态为 `open → handling → resolved/ignored`，所有处理动作写入操作日志。
- 临期提醒每 30 分钟扫描一次；外部通知每 5 分钟尝试投递。
- 用户可以独立设置站内、邮件、企业微信、钉钉和提前提醒小时数。
- 邮件与机器人配置缺失时不会影响站内信和核心业务事务。

## 权限增量

V2.0 新增：`risk:view`、`risk:handle`、`notification:view`、`import:manage`、`export:download`、`analytics:view`。前端菜单只改善体验，后端权限依赖与项目数据范围仍是安全边界。

## API 与文档

- 健康检查：`GET /health`
- Swagger：`/docs`
- ReDoc：`/redoc`
- 业务 API 前缀：`/api/v1`

详细清单见 [docs/API.md](docs/API.md)，数据库见 [docs/DATABASE.md](docs/DATABASE.md)，架构见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，V2 验收范围见 [docs/V2_SCOPE.md](docs/V2_SCOPE.md)，新增与修改文件见 [docs/V2_FILE_MANIFEST.md](docs/V2_FILE_MANIFEST.md)。

## 维护者自行验证

本次交付没有执行以下命令。维护者完成环境和数据库准备后可自行运行：

```powershell
# 后端已有测试
cd backend
pytest

# 前端类型检查和构建
cd ../frontend
npm run type-check
npm run build
```

建议按“V1 回归 → 数据迁移 → 新权限 → 驾驶舱 → 看板增强 → 风险扫描/关闭 → 站内通知 → Excel 导入错误明细 → 三类导出 → Worker/Beat 外部通知”的顺序验收。
