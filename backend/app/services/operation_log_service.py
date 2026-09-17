import json
import logging
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.models.operation_log import OperationLog

logger = logging.getLogger(__name__)

IGNORED_CHANGE_FIELDS = {"created_at", "updated_at", "password_hash"}
ACTION_LABELS = {
    "create": "新增了",
    "update": "修改了",
    "delete": "删除了",
    "change_password": "修改了登录密码",
    "add_member": "添加了项目成员",
    "remove_member": "移除了项目成员",
    "approve": "审批通过了",
    "reject": "驳回了",
    "create_organization": "新增了",
    "update_organization": "修改了",
    "delete_organization": "删除了",
    "assign_user_roles": "调整了",
    "update_role_permissions": "调整了",
    "create_department": "新增了",
    "update_department": "修改了",
    "delete_department": "删除了",
    "create_auto_approved": "创建并自动审批了",
    "create_draft": "创建了草稿",
    "submit_for_approval": "提交审批了",
    "auto_approve": "自动审批了",
    "request_hours": "申请追加了",
    "approve_hours": "批准了",
    "reject_hours": "驳回了",
    "create_personal_time": "新增了",
    "withdraw_personal_time": "撤回了",
    "submit": "提交了",
    "confirm": "确认了",
    "withdraw": "撤回了",
    "cancel": "取消了",
    "move": "调整时间了",
    "batch_submit": "批量提交了",
    "copy_week": "复制周排期生成了",
    "import": "执行了",
    "sync": "执行了",
    "handle": "处理了",
}
OBJECT_LABELS = {
    "user": "用户",
    "project": "项目",
    "task": "任务",
    "execution_record": "执行记录",
    "organization": "组织",
    "department": "部门",
    "schedule": "人力预约",
    "personal_time_block": "个人时间安排",
    "task_evaluation": "任务评价",
    "work_calendar_day": "工作日历",
    "project_member": "项目成员",
    "project_hour_request": "项目追加工时申请",
    "schedule_booking": "人力预约",
    "role": "角色",
    "import_job": "数据导入任务",
    "risk_scan": "风险扫描",
    "risk_record": "风险记录",
}
FIELD_LABELS = {
    "employee_no": "员工号",
    "name": "名称/姓名",
    "email": "邮箱",
    "department_id": "部门",
    "organization_id": "组织",
    "supervisor_id": "直属主管",
    "role_ids": "系统角色",
    "permission_ids": "功能权限",
    "status": "状态",
    "approval_status": "审批状态",
    "manager_id": "项目经理",
    "owner_id": "主负责人",
    "owner_ids": "负责人",
    "planned_start": "计划开始日期",
    "planned_end": "计划结束日期",
    "actual_start": "实际开始日期",
    "actual_end": "实际结束日期",
    "actual_hours": "实际工时",
    "estimated_hours": "预计工时",
    "budget_hours": "项目工时额度",
    "member_ids": "项目成员",
}


def describe_change(
    action: str,
    object_type: str,
    object_id: str | int,
    before_data: dict[str, Any] | None,
    after_data: dict[str, Any] | None,
) -> str:
    action_label = ACTION_LABELS.get(action, action)
    object_label = OBJECT_LABELS.get(object_type, object_type)
    if action == "change_password":
        return f"修改了{object_label}#{object_id}的登录密码"
    before = before_data or {}
    after = after_data or {}
    fields = []
    for key in sorted(set(before) | set(after)):
        if key in IGNORED_CHANGE_FIELDS or before.get(key) == after.get(key):
            continue
        if key not in before:
            fields.append(f"{FIELD_LABELS.get(key, key)}={after.get(key)}")
        elif key not in after:
            fields.append(f"{FIELD_LABELS.get(key, key)}（原值 {before.get(key)}）")
        else:
            fields.append(
                f"{FIELD_LABELS.get(key, key)}: {before.get(key)} → {after.get(key)}"
            )
    suffix = "；".join(fields[:10])
    if len(fields) > 10:
        suffix += f"；另有 {len(fields) - 10} 项变化"
    return f"{action_label}{object_label}#{object_id}" + (f"：{suffix}" if suffix else "")


def log_operation(
    db: Session,
    *,
    operator_id: int | None,
    module: str,
    action: str,
    object_type: str,
    object_id: str | int,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
) -> None:
    encoded_before = jsonable_encoder(before_data) if before_data is not None else None
    encoded_after = jsonable_encoder(after_data) if after_data is not None else None
    try:
        with db.begin_nested():
            db.add(
                OperationLog(
                    operator_id=operator_id,
                    module=module,
                    action=action,
                    object_type=object_type,
                    object_id=str(object_id),
                    before_data=encoded_before,
                    after_data=encoded_after,
                    reason=reason,
                    ip_address=ip_address,
                )
            )
            db.flush()
    except Exception:
        logger.exception("failed to persist operation log")
    logger.info(
        "operation %s",
        json.dumps(
            {
                "operator_id": operator_id,
                "module": module,
                "action": action,
                "object_type": object_type,
                "object_id": str(object_id),
                "summary": describe_change(
                    action, object_type, object_id, encoded_before, encoded_after
                ),
                "reason": reason,
                "ip_address": ip_address,
            },
            ensure_ascii=False,
            default=str,
        ),
    )
