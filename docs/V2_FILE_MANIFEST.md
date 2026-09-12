# V2.0 文件归档清单

## 版本与部署

- `VERSION`、`CHANGELOG.md`、根 `README.md`
- `.env.example`、`backend/.env.example`
- `docker-compose.yml`
- `backend/requirements.txt`
- `frontend/package.json`、`frontend/package-lock.json`

## 后端新增文件

```text
backend/alembic/versions/20260910_0002_v2_features.py
backend/alembic/versions/20260911_0003_safe_deletion.py
backend/alembic/versions/20260911_0004_project_approval_and_work_calendar.py
backend/app/models/import_job.py
backend/app/models/notification.py
backend/app/models/work_calendar.py
backend/app/repositories/risk_repository.py
backend/app/schemas/import_export.py
backend/app/schemas/notification.py
backend/app/schemas/risk.py
backend/app/schemas/work_calendar.py
backend/app/services/import_export_service.py
backend/app/services/notification_service.py
backend/app/services/risk_service.py
backend/app/services/work_calendar_service.py
backend/app/api/v1/data_exchange.py
backend/app/api/v1/notifications.py
backend/app/api/v1/risks.py
backend/app/api/v1/work_calendar.py
backend/app/tasks/__init__.py
backend/app/tasks/celery_app.py
backend/app/tasks/notification_tasks.py
backend/app/tasks/risk_tasks.py
```

后端同时修改了项目模型/Schema/Repository/Service/API、任务创建限制、人力预约状态机与配额校验、组织 L3 校验、Excel 项目导入、主路由和初始化权限。

## 前端新增文件

```text
frontend/src/api/data-exchange.ts
frontend/src/api/notification.ts
frontend/src/api/risk.ts
frontend/src/api/work-calendar.ts
frontend/src/types/data-exchange.ts
frontend/src/types/notification.ts
frontend/src/types/risk.ts
frontend/src/types/work-calendar.ts
frontend/src/stores/notification.ts
frontend/src/views/analytics/AnalyticsView.vue
frontend/src/views/data-exchange/DataExchangeView.vue
frontend/src/views/notification/NotificationCenterView.vue
frontend/src/views/risk/RiskCenterView.vue
frontend/src/views/workload/WorkloadAnalysisView.vue
frontend/src/views/schedule/WorkCalendarView.vue
```

前端同时修改了项目列表/详情、任务创建、驾驶舱本人预约快捷审批、共享看板、时间点式半小时时间轴、工作/非工作/法定节假日配色、预约表单、组织 L3 字段、通知中心与右上角未读角标同步、导航/顶栏、路由、项目/排期 API 与类型。

## 文档

```text
README.md
backend/README.md
frontend/README.md
docs/API.md
docs/ARCHITECTURE.md
docs/DATABASE.md
docs/V2_SCOPE.md
docs/V2_MIGRATION.md
docs/V2_FILE_MANIFEST.md
```

## 交付约束记录

本次只做文件创建、编辑与归档核对。没有安装依赖，没有执行数据库迁移或初始化脚本，没有生成运行时 Excel 文件，没有运行测试或构建，也没有启动任何服务。
