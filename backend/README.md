# V2.0 后端

FastAPI 后端沿用 `Router → Service → Repository → Model` 分层，并在 V2.0 增加 Celery 后台任务层和 Excel 数据交换服务。

## 主要模块

- `app/api/v1`：认证、基础主数据、项目/任务/排期/执行，以及 V2 风险、通知、数据交换和分析接口。
- `app/services/risk_service.py`：风险发现、指纹去重、数据范围和处理闭环。
- `app/services/notification_service.py`：站内信与邮件/机器人投递；通知偏好接口已移除。
- `app/services/import_export_service.py`：标准模板、逐行导入和业务报表导出。
- `app/tasks`：风险扫描、临期提醒、外部通知和预约状态推进的 Celery 任务。
- `alembic/versions/20260910_0002_v2_features.py`：V1.0 到 V2.0 增量迁移。
- `app/services/project_service.py`：项目草稿/直属主管审批、项目经理兼具 L3/管理员角色时自动通过、项目额度和追加工时 L3 审批。
- `app/services/work_calendar_service.py`：工作日、法定节假日、上午/下午时段与自动工时校验。
- `alembic/versions/20260911_0004_project_approval_and_work_calendar.py`：项目审批、额度、工作日历及 L3/L4 增量迁移。
- `app/services/personal_time_service.py`：本人培训、会议、休假、外出、出差等个人占用的创建、冲突校验与撤回。
- `alembic/versions/20260912_0005_personal_time_blocks.py`：个人时间安排表、外键和冲突查询索引。
- `alembic/versions/20260914_0006_employee_profiles_and_role_sources.py`：历史迁移，曾引入人员档案和角色来源字段。
- `alembic/versions/20260914_0007_business_rules_alignment.py`：增加 HRDB 来源标识、直属主管审批人、任务/执行/通知软删除，并归一任务状态和默认成员角色。
- `alembic/versions/20260915_0008_project_manager_membership.py`：为历史项目补齐项目经理固定成员关系，使所有预约统一依赖有效项目成员。
- `alembic/versions/20260916_0009_simplify_user_schema.py`：删除兼容用户名、手机号、人员档案和角色来源字段，收敛为当前用户模型。
- `alembic/versions/20260916_0010_task_multi_assignees.py`：新增任务多人负责人关系并回填历史负责人。
- `alembic/versions/20260917_0011_task_execution_dates.py`：任务计划和执行实际日期由 DATETIME 收敛为 DATE。
- `alembic/versions/20260918_0012_permission_status_alignment.py`：补齐 L3/L4 权限，移除项目成员项目编辑权，并按最新有效执行记录修复开放项目的任务状态。
- `app/services/status_sync_service.py`：按执行记录汇总任务、父任务和项目状态。

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

除 V1 配置外，V2 新增 `REDIS_URL`、`RISK_STALE_DAYS`、`IMPORT_MAX_MB`、`IMPORT_DEFAULT_PASSWORD`、`NOTIFICATION_UPCOMING_HOURS`、`SMTP_*`、`WECOM_WEBHOOK_URL` 和 `DINGTALK_WEBHOOK_URL`。通知不再提供用户偏好；临期小时数和外部渠道均由环境配置统一控制，未配置外部渠道时站内通知可正常独立工作。

## 数据迁移

不要修改已经归档的 `20260909_0001_initial_schema.py`。从 V1 升级时执行：

```powershell
alembic upgrade head
python -m scripts.init_data
```

第二条命令会补齐 V2 权限和五类系统角色默认授权，且可重复执行。配置名 `INITIAL_ADMIN_USERNAME` 为兼容已有部署而保留，但它的值只作为管理员的 `employee_no` 登录账号使用。`INITIAL_ADMIN_PASSWORD` 只用于首次创建管理员，不会在重启或重复执行初始化脚本时覆盖已有密码。

## 用户字段与系统角色

- `users.id` 是内部数字主键；`users.employee_no` 是唯一员工号及唯一登录账号。
- 用户业务字段只保留 `employee_no`、`name`、`email`、`department_id`、`organization_id`、`supervisor_id`；密码哈希、状态、软删除标记和时间戳是系统运行字段。
- 新建和导入用户必须设置有效部门与直属主管；最高级主管仅由维护者直接写入数据库。删除用户前必须先移交直属下属和部门/组织管理关系。
- `user_roles` 只维护用户与系统角色的直接关联，不再区分人工来源和人事职级来源。
- 系统角色固定保留超级管理员、L3（代码 `department_manager`）、L4（代码 `functional_manager`）、项目经理和项目成员。
- 用户没有任何角色时，默认授予 `project_member`。
- 当前版本只使用 MySQL，不包含人员档案、人事职级、岗位或正式 HRDB 人员同步模型。
- 超级管理员/L3 可查看和管理全部项目任务；L4 查看本人及全部层级下属相关项目任务；项目经理和项目成员查看本人负责、参与或承担任务的相关项目。仅项目负责人或全局角色维护项目核心数据，执行记录默认仍只允许本人维护，超级管理员可全局维护。

## 项目与预约状态规则

- 项目经理、L4、L3 或超级管理员可创建项目，项目编号自动生成；普通创建人提交时由 `users.supervisor_id` 对应的有效直属主管审批，L3/超级管理员创建时自动通过。
- 创建项目必须指定至少一名普通成员；项目经理自动作为 `manager` 固定成员写入 `project_members` 且不能移除。项目获批后才能继续添加成员、创建任务和预约人力。
- 额度不足由项目经理创建 `project_hour_requests`，仍由项目所属部门当前 L3 审批。
- 新预约直接为 `pending`，仅 `user_id` 对应本人可确认或拒绝；原提交人可在确认前撤回为 `withdrawn`。
- 已确认预约到达开始时间后自动变为 `running`，到达结束时间后自动变为 `completed`；超过结束时间仍未确认的预约自动变为 `cancelled`。Celery 每 5 分钟推进一次，共享看板和预约待办读取时也会即时校正。
- 每个登录用户可创建自己的 `training/meeting/leave/out_of_office/business_trip/other` 个人时间安排，且只有本人可撤回；生效中的个人安排与项目预约互斥。
- 日程可见范围为：超级管理员/L3 全量，L4 为本人及全部层级下属，项目经理为本人和自己负责项目的有效成员，普通成员为本人；多角色按范围并集处理。
- 预约必须同时满足项目成员关系和操作者范围：项目负责人可使用本人负责且已审批的项目预约有效成员，L3/超级管理员拥有全局预约管理权；项目负责人预约自己时自动确认。
- MySQL 连接会话、业务时间和应用日志统一使用北京时间；工作日历、负载和风险后台逻辑保留，但当前 UI 隐藏。
- 单条创建、编辑、旧草稿提交、确认、拖动、批量创建和复制周都会同时检查项目预约与个人安排；同一用户行锁用于串行化并发占用写入。
- 所有预约写接口都在服务端重新计算工时，并强制工作日、半小时粒度、`08:30-12:00`/`13:00-17:30` 边界。
- 任务计划必须位于项目计划日期范围内，预约必须同时位于项目和任务计划范围内；结束项目或任务前必须先处理未结束任务、预约和待审批工时申请。
- 任务计划和执行实际起止日期按天保存，结束日期不得早于开始日期且实际日期不能晚于北京时间当天；执行工时可按工作日自动计算，显式工时不得超过所选日期的工作日容量。项目实际起止日期由有效执行记录自动汇总，不接受手工覆盖。
- 任务状态始终取最新一条未删除执行记录，删除最新记录后回退到上一条；父任务自动汇总。项目运行态随任务联动，但全部任务完成不会自动关闭项目，必须由项目负责人、L3 或超级管理员手动确认完成。
- 本项目负责人、L3 或超级管理员提交首条任务评价后，项目进入评价锁定阶段；执行记录不能再新增、修改或删除，避免状态回退后遗留失效评价。
- 应用操作日志实时写入数据库并同步归档到 `logs/YYYY-MM-DD/app-HH.log`，每小时自动切换文件。
- `work_calendar_days` 覆盖普通星期判断；迁移已内置 2026 年法定安排，后续年度由 L3/超级管理员维护。

## 测试说明

本次 V2.0 文件交付没有安装依赖、执行迁移或运行测试。维护者配置独立测试数据库后，可自行运行 `pytest`，并按照根目录 `docs/V2_SCOPE.md` 增补/执行 V2 验收。
