# V1.0 → V2.0 升级说明

## 升级前

1. 停止 V1 后端写流量。
2. 备份 MySQL 数据库、`.env` 和部署配置。
3. 记录当前 Alembic revision，应为 `20260909_0001`。
4. 为生产环境设置新的 `IMPORT_DEFAULT_PASSWORD`，不要保留示例值。
5. 准备 Redis；外部通知可以暂不配置。

## 文件与依赖变化

后端新增运行依赖：`openpyxl`、`celery[redis]`、`redis`。前端没有新增依赖，但 `package.json` 和 lockfile 项目版本更新为 `2.0.0`。

维护者自行执行：

```powershell
cd backend
pip install -r requirements.txt
alembic upgrade head
python -m scripts.init_data
```

不要对生产库运行 `alembic stamp head` 代替真实迁移。

## 迁移内容

`20260910_0002_v2_features.py` 会：

- 为 `schedule_bookings` 添加 `source_booking_id`、`version` 和外键/索引。
- 为 `risk_records` 添加指纹、标题、来源数据、检测/到期/解决时间和唯一索引。
- 新建 `notifications`、`notification_preferences`、`import_jobs`。

V1 已存在的风险记录因 `fingerprint` 可空而兼容；新扫描记录使用非空稳定指纹。

`20260911_0003_safe_deletion.py` 为用户增加软删除字段。`20260911_0004_project_approval_and_work_calendar.py` 会：

- 为项目增加总工时、审批状态、创建人、审批人、审批时间和意见。
- 将升级前已有项目视为已审批，并以“任务预计工时合计”和“已有有效预约工时合计”较大值作为初始额度。
- 新建追加工时申请和工作日历表，写入索引、外键和审计时间。
- 根据国务院正式通知内置 2026 年法定节假日和调休工作日。
- 将系统角色显示名从“部门主管/职能主管”更新为 `L3/L4`，并增加 `calendar:manage` 权限。

## 初始化权限

迁移后必须再次执行 `python -m scripts.init_data`。脚本会补齐：

- `risk:view`、`risk:handle`
- `notification:view`
- `import:manage`、`export:download`
- `analytics:view`
- `calendar:manage`

系统角色的权限会按 V2 默认集合重建，`calendar:manage` 默认授予超级管理员和 L3。如果生产环境曾直接修改系统角色，请先记录差异，升级后通过角色权限页面重新调整；自定义非系统角色不会被删除。

## 升级后的必做业务配置

1. 给项目创建人分配“项目经理”角色，并确认用户所属部门正确。
2. 为每个需要创建项目的部门设置一名有效 L3；该用户必须同时拥有 L3 角色。
3. 检查已有项目自动生成的工时额度，额度为 0 的历史项目如需继续预约，应先由项目经理提交追加工时申请。
4. 每年国务院发布下一年度放假通知后，由 L3/超级管理员在“工作日历”维护节假日和调休工作日。

## 服务启动顺序

1. MySQL、Redis。
2. 执行 Alembic 和初始化脚本。
3. FastAPI 后端。
4. Celery Worker。
5. Celery Beat（集群只运行一个 Beat 实例）。
6. 前端/Nginx。

## 回滚提醒

代码可通过版本控制回退；数据库降级会永久删除追加工时申请、工作日历、通知、偏好、导入任务及新增字段数据。只有在确认备份可用、V2 数据可丢弃时才执行。

## 本次交付状态

本次仅完成文件创建、编辑和归档。未安装依赖、未执行迁移、未运行初始化脚本、未构建、未测试、未启动服务。
