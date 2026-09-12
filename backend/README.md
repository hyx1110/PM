# V2.0 后端

FastAPI 后端沿用 `Router → Service → Repository → Model` 分层，并在 V2.0 增加 Celery 后台任务层和 Excel 数据交换服务。

## 主要模块

- `app/api/v1`：认证、基础主数据、项目/任务/排期/执行，以及 V2 风险、通知、数据交换和分析接口。
- `app/services/risk_service.py`：风险发现、指纹去重、数据范围和处理闭环。
- `app/services/notification_service.py`：站内信、偏好与邮件/机器人投递。
- `app/services/import_export_service.py`：标准模板、逐行导入和业务报表导出。
- `app/tasks`：风险扫描、临期提醒和外部通知的 Celery 任务。
- `alembic/versions/20260910_0002_v2_features.py`：V1.0 到 V2.0 增量迁移。
- `app/services/project_service.py`：项目/L3 审批、项目额度和追加工时审批。
- `app/services/work_calendar_service.py`：工作日、法定节假日、上午/下午时段与自动工时校验。
- `alembic/versions/20260911_0004_project_approval_and_work_calendar.py`：项目审批、额度、工作日历及 L3/L4 增量迁移。

## 维护者执行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m scripts.init_data
uvicorn app.main:app --reload
```

后台任务：

```powershell
celery -A app.tasks.celery_app:celery_app worker --loglevel=INFO
celery -A app.tasks.celery_app:celery_app beat --loglevel=INFO
```

## 配置重点

除 V1 配置外，V2 新增 `REDIS_URL`、`RISK_STALE_DAYS`、`IMPORT_MAX_MB`、`IMPORT_DEFAULT_PASSWORD`、`SMTP_*`、`WECOM_WEBHOOK_URL` 和 `DINGTALK_WEBHOOK_URL`。外部通知均为可选，未配置时站内通知可正常独立工作。

## 数据迁移

不要修改已经归档的 `20260909_0001_initial_schema.py`。从 V1 升级时执行：

```powershell
alembic upgrade head
python -m scripts.init_data
```

第二条命令会补齐 V2 权限和系统角色默认授权，且可重复执行。

## 项目与预约状态规则

- 只有项目经理本人可以提交由自己负责的项目；所属部门必须先设置具有 `department_manager` 角色的有效 L3。
- 项目经 L3 批准后才能添加成员、创建任务和预约人力；总预约工时不得突破项目额度。
- 额度不足由项目经理创建 `project_hour_requests`，仍由项目所属部门当前 L3 审批。
- 新预约直接为 `pending`，仅 `user_id` 对应本人可确认或拒绝；原提交人可在确认前撤回为 `withdrawn`。
- 所有预约写接口都在服务端重新计算工时，并强制工作日、半小时粒度、`08:30-12:00`/`13:00-17:30` 边界。
- `work_calendar_days` 覆盖普通星期判断；迁移已内置 2026 年法定安排，后续年度由 L3/超级管理员维护。

## 测试说明

本次 V2.0 文件交付没有安装依赖、执行迁移或运行测试。维护者配置独立测试数据库后，可自行运行 `pytest`，并按照根目录 `docs/V2_SCOPE.md` 增补/执行 V2 验收。
