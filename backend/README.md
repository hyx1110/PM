# V2.0 后端

FastAPI 后端沿用 `Router → Service → Repository → Model` 分层，并在 V2.0 增加 Celery 后台任务层和 Excel 数据交换服务。

## 主要模块

- `app/api/v1`：认证、基础主数据、项目/任务/排期/执行，以及 V2 风险、通知、数据交换和分析接口。
- `app/services/risk_service.py`：风险发现、指纹去重、数据范围和处理闭环。
- `app/services/notification_service.py`：站内信、偏好与邮件/机器人投递。
- `app/services/import_export_service.py`：标准模板、逐行导入和业务报表导出。
- `app/tasks`：风险扫描、临期提醒和外部通知的 Celery 任务。
- `alembic/versions/20260910_0002_v2_features.py`：V1.0 到 V2.0 增量迁移。
- `app/services/project_service.py`：项目草稿/直属主管审批、L3/管理员自动通过、项目额度和追加工时 L3 审批。
- `app/services/work_calendar_service.py`：工作日、法定节假日、上午/下午时段与自动工时校验。
- `alembic/versions/20260911_0004_project_approval_and_work_calendar.py`：项目审批、额度、工作日历及 L3/L4 增量迁移。
- `app/services/personal_time_service.py`：本人培训、会议、休假、外出、出差等个人占用的创建、冲突校验与撤回。
- `alembic/versions/20260912_0005_personal_time_blocks.py`：个人时间安排表、外键和冲突查询索引。
- `app/models/employee_profile.py`：与登录账号和 RBAC 分离的正式人员档案，一名员工对应一个岗位编号。
- `app/services/employee_profile_service.py`：维护人员档案，并将正式 `department_manager`/`management_manager` 职级同步为系统 L3/L4 自动授权。
- `alembic/versions/20260914_0006_employee_profiles_and_role_sources.py`：增加员工号、人员档案以及人工/职级自动角色来源。
- `alembic/versions/20260914_0007_business_rules_alignment.py`：增加 HRDB 来源标识、直属主管审批人、任务/执行/通知软删除，并归一任务状态和默认成员角色。
- `alembic/versions/20260915_0008_project_manager_membership.py`：为历史项目补齐项目经理固定成员关系，使所有预约统一依赖有效项目成员。

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

第二条命令会补齐 V2 权限和五类系统角色默认授权，且可重复执行。为兼容已有环境，`INITIAL_ADMIN_USERNAME` 仍保留原变量名，但其值会同时写入管理员的 `employee_no` 和兼容字段 `username`。

## 人员档案与系统角色

- `users.id` 继续作为内部数字主键；`users.employee_no` 是唯一员工号及登录账号，`users.username` 仅作为兼容字段并强制保持同值。
- `users.department_id`、`organization_id`、`supervisor_id` 分别表示部门、组织和直属上级；`employee_profiles.position_id` 一人一个且不能被其他用户复用。
- 正式人事职级保存在 `employee_profiles.hr_management_level`，不直接承担鉴权。`department_manager` 自动授予系统角色代码 `department_manager`（显示 L3），`management_manager` 自动授予 `functional_manager`（显示 L4）。
- `user_roles.is_manual` 和 `is_hr_auto` 分别记录人工分配与职级映射来源。同一个角色可以同时具有两个来源；职级变化仅清除自动来源，不会撤销人工角色。
- 超级管理员、L3、L4、项目经理、项目成员仍是完整保留的五类系统权限角色。当前版本只建立 MySQL 测试架构，不导入正式人员数据。
- 用户没有任何人工或 HR 自动角色时，默认授予 `project_member`。
- `data_source=hrdb` 的人员档案、部门和组织只能由未来的 HRDB 同步程序更新；本版本不包含正式连接器。
- 项目可见范围与团队管理范围分离：项目经理仅管理本人负责项目，L3/L4 管理本部门项目，普通成员在参与项目中只读取本人任务、日程、预约、执行和风险。

## 项目与预约状态规则

- 项目经理可保存草稿，提交时由 `users.supervisor_id` 对应的有效直属主管审批；L3 或超级管理员创建时系统自动通过。
- 创建项目必须指定至少一名普通成员；项目经理自动作为 `manager` 固定成员写入 `project_members` 且不能移除。项目获批后才能继续添加成员、创建任务和预约人力。
- 额度不足由项目经理创建 `project_hour_requests`，仍由项目所属部门当前 L3 审批。
- 新预约直接为 `pending`，仅 `user_id` 对应本人可确认或拒绝；原提交人可在确认前撤回为 `withdrawn`。
- 每个登录用户可创建自己的 `training/meeting/leave/out_of_office/business_trip/other` 个人时间安排，且只有本人可撤回；生效中的个人安排与项目预约互斥。
- 日程可见范围为：超级管理员/L3 全量，L4 为本人和直属下属，项目经理为本人和自己负责项目的有效成员，普通成员为本人；多角色按范围并集处理。
- 预约必须同时满足项目成员关系和操作者范围：项目经理仅预约本人负责项目成员，L3/L4 仅预约 `supervisor_id` 指向自己的直属下属，超级管理员保留全局权限。
- 单条创建、编辑、旧草稿提交、确认、拖动、批量创建和复制周都会同时检查项目预约与个人安排；同一用户行锁用于串行化并发占用写入。
- 所有预约写接口都在服务端重新计算工时，并强制工作日、半小时粒度、`08:30-12:00`/`13:00-17:30` 边界。
- `work_calendar_days` 覆盖普通星期判断；迁移已内置 2026 年法定安排，后续年度由 L3/超级管理员维护。

## 测试说明

本次 V2.0 文件交付没有安装依赖、执行迁移或运行测试。维护者配置独立测试数据库后，可自行运行 `pytest`，并按照根目录 `docs/V2_SCOPE.md` 增补/执行 V2 验收。
