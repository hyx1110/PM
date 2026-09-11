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
backend/app/models/import_job.py
backend/app/models/notification.py
backend/app/repositories/risk_repository.py
backend/app/schemas/import_export.py
backend/app/schemas/notification.py
backend/app/schemas/risk.py
backend/app/services/import_export_service.py
backend/app/services/notification_service.py
backend/app/services/risk_service.py
backend/app/api/v1/data_exchange.py
backend/app/api/v1/notifications.py
backend/app/api/v1/risks.py
backend/app/tasks/__init__.py
backend/app/tasks/celery_app.py
backend/app/tasks/notification_tasks.py
backend/app/tasks/risk_tasks.py
```

后端同时修改了主路由、报表/排期 API 与 Service、风险/排期模型、排期 Schema、配置、初始化权限和应用版本。

## 前端新增文件

```text
frontend/src/api/data-exchange.ts
frontend/src/api/notification.ts
frontend/src/api/risk.ts
frontend/src/types/data-exchange.ts
frontend/src/types/notification.ts
frontend/src/types/risk.ts
frontend/src/views/analytics/AnalyticsView.vue
frontend/src/views/data-exchange/DataExchangeView.vue
frontend/src/views/notification/NotificationCenterView.vue
frontend/src/views/risk/RiskCenterView.vue
frontend/src/views/workload/WorkloadAnalysisView.vue
```

前端同时修改了驾驶舱、共享看板、人员排期行、导航/顶栏、路由、请求客户端、排期/报表 API 与类型。

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

