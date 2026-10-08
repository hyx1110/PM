import json
import logging
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.models.operation_log import OperationLog
from app.services.business_text_service import field_reference, load_reference_labels, reference_label

logger = logging.getLogger(__name__)

IGNORED_CHANGE_FIELDS = {"id", "version", "created_at", "updated_at", "password_hash", "_display_labels"}
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
    "request_resources": "申请了",
    "approve_resources": "批准了",
    "apply_resources": "应用了已审批资源变更到",
    "reject_resources": "驳回了",
    "withdraw_resources": "撤回了",
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
    "project_initiation_report": "项目立项报告",
    "task": "任务",
    "execution_record": "执行记录",
    "overtime_request": "加班申请",
    "organization": "组织",
    "department": "部门",
    "schedule": "人力预约",
    "personal_time_block": "个人时间安排",
    "task_evaluation": "任务评价",
    "project_evaluation": "项目评价",
    "work_calendar_day": "工作日历",
    "project_member": "项目成员",
    "project_resource_request": "项目资源申请",
    "project_hour_request": "项目追加工时申请（历史）",
    "schedule_booking": "人力预约",
    "role": "角色",
    "import_job": "数据导入任务",
    "risk_scan": "风险扫描",
    "risk_record": "风险记录",
}
FIELD_LABELS = {
    "filename": "附件名称",
    "size_bytes": "文件大小（字节）",
    "uploaded_by": "上传人",
    "user_id": "人员",
    "project_id": "所属项目",
    "task_id": "关联任务",
    "parent_id": "上级任务/组织",
    "start_time": "开始时间",
    "end_time": "结束时间",
    "planned_hours": "预约工时",
    "created_by": "创建人",
    "requested_by": "申请人",
    "approved_by": "审批人",
    "remark": "备注",
    "description": "说明",
    "rejection_reason": "拒绝/撤回原因",
    "time_type": "日程类型",
    "is_deleted": "已删除",
    "joined_at": "加入项目时间",
    "left_at": "退出项目时间",
    "source_booking_id": "原预约",
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
    "approval_note": "审批意见",
    "submitted_at": "提交审批时间",
    "approved_at": "审批时间",
    "manager_id": "项目经理",
    "owner_id": "主要项目成员",
    "owner_ids": "项目成员",
    "planned_start": "计划开始日期",
    "planned_end": "计划结束日期",
    "actual_start": "实际开始日期",
    "actual_end": "实际结束日期",
    "actual_hours": "实际工时",
    "estimated_hours": "预计工时",
    "budget_hours": "项目工时额度",
    "member_ids": "项目成员",
    "requested_hours": "追加工时",
    "original_planned_end": "申请时原计划结束日期",
    "requested_planned_end": "申请延期至",
    "add_member_ids": "新增成员",
    "remove_member_ids": "移除成员",
    "reason": "申请原因",
    "overtime_request_id": "关联加班申请",
    "hours": "申请工时",
    "approver_id": "审批人",
    "review_note": "审批说明",
    "reviewed_by": "实际审批人",
    "reviewed_at": "审批时间",
    "withdrawn_at": "撤回时间",
}


STATUS_LABELS = {
    "not_required": "无需单独审批",
    "pending": "待审批", "approved": "已批准", "rejected": "已驳回", "withdrawn": "已撤回",
    "draft": "草稿", "confirmed": "已确认", "changed": "改期待确认", "cancelled": "已取消",
    "running": "进行中", "not_started": "未开始", "completed": "已完成", "delayed": "已逾期",
    "active": "启用", "inactive": "停用", "disabled": "停用",
}


def _display_value(key: str, value, object_type: str, labels: dict) -> str:
    if value is None:
        return "未设置"
    kind = field_reference(key, object_type)
    if kind:
        if isinstance(value, list):
            return "、".join(reference_label(labels, kind, uid) for uid in value) or "无"
        return reference_label(labels, kind, value)
    if key in {"status", "approval_status"}:
        if object_type in {"schedule", "schedule_booking"}:
            return {"pending": "待本人确认", "rejected": "已拒绝"}.get(value, STATUS_LABELS.get(value, str(value)))
        if object_type == "personal_time_block" and value == "active":
            return "生效中"
        return STATUS_LABELS.get(value, str(value))
    if key == "time_type":
        return {"training": "培训", "meeting": "会议", "leave": "休假", "out_of_office": "外出", "business_trip": "出差", "other": "其他安排"}.get(value, str(value))
    if isinstance(value, bool):
        return "是" if value else "否"
    if key.endswith("_id") or key.endswith("_ids"):
        return "有关联记录（见结构化详情）" if value else "无"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    text = str(value)
    if key.endswith(("_time", "_at")):
        return text.replace("T", " ")
    return text


def _object_description(object_type: str, object_id, data: dict, labels: dict) -> str:
    object_label = OBJECT_LABELS.get(object_type, object_type)
    if data.get("name"):
        if object_type == "task" and data.get("project_id"):
            return f"项目“{reference_label(labels, 'project', data['project_id'])}”的任务“{data['name']}”"
        return f"{object_label}“{data['name']}”"
    if object_type == "work_calendar_day":
        return f"工作日历（{data.get('date') or object_id}）"
    if object_type in {"user", "project", "task", "department", "organization", "role"}:
        return f"{object_label}“{reference_label(labels, object_type, object_id)}”"
    context = []
    task_project = labels.get(f"task_project:{data.get('task_id')}")
    if data.get("project_id"):
        context.append(f"项目“{reference_label(labels, 'project', data['project_id'])}”")
    elif data.get("task_id") and task_project:
        context.append(f"项目“{task_project}”")
    if data.get("task_id"):
        context.append(f"任务“{reference_label(labels, 'task', data['task_id'])}”")
    if data.get("user_id"):
        prefix = "被预约人" if object_type in {"schedule", "schedule_booking"} else "人员"
        context.append(f"{prefix}“{reference_label(labels, 'user', data['user_id'])}”")
    if data.get("start_time") and data.get("end_time"):
        context.append(f"{str(data['start_time']).replace('T', ' ')} 至 {str(data['end_time']).replace('T', ' ')}")
    return object_label + (f"（{'；'.join(context)}）" if context else "" if data else "（历史关联信息未留存）")


def describe_change(
    action: str,
    object_type: str,
    object_id: str | int,
    before_data: dict[str, Any] | None,
    after_data: dict[str, Any] | None,
    labels: dict[str, str] | None = None,
) -> str:
    action_label = ACTION_LABELS.get(action, action)
    if object_type in {"schedule", "schedule_booking"} and action == "reject":
        action_label = "拒绝了"
    before = before_data or {}
    after = after_data or {}
    before_labels = {**(labels or {}), **(before.get("_display_labels") or {})}
    after_labels = {**(labels or {}), **(after.get("_display_labels") or {})}
    target = _object_description(object_type, object_id, after or before, after_labels if after else before_labels)
    if action == "change_password":
        return f"修改了{target}的登录密码"
    fields = []
    for key in sorted(set(before) | set(after)):
        if key in IGNORED_CHANGE_FIELDS or before.get(key) == after.get(key):
            continue
        if key not in before:
            fields.append(f"{FIELD_LABELS.get(key, key)}={_display_value(key, after.get(key), object_type, after_labels)}")
        elif key not in after:
            fields.append(f"{FIELD_LABELS.get(key, key)}（原值 {_display_value(key, before.get(key), object_type, before_labels)}）")
        else:
            fields.append(
                f"{FIELD_LABELS.get(key, key)}: {_display_value(key, before.get(key), object_type, before_labels)} → {_display_value(key, after.get(key), object_type, after_labels)}"
            )
    suffix = "；".join(fields[:10])
    if len(fields) > 10:
        suffix += f"；另有 {len(fields) - 10} 项变化"
    return f"{action_label}{target}" + (f"：{suffix}" if suffix else "")


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
    if encoded_before is None and encoded_after is None:
        # Even actions without field changes (e.g. password changes) retain
        # names, but never store the password or fabricate business fields.
        encoded_after = {}
    labels = {}
    try:
        with db.begin_nested():
            labels = load_reference_labels(db, [(object_type, object_id, encoded_before, encoded_after), ("user", operator_id, None, None)])
            for snapshot in (encoded_before, encoded_after):
                if snapshot is not None:
                    snapshot["_display_labels"] = {**labels, **(snapshot.get("_display_labels") or {})}
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
                "summary": (reference_label(labels, "user", operator_id) if operator_id is not None else "系统") + " " + describe_change(
                    action, object_type, object_id, encoded_before, encoded_after, labels
                ),
                "reason": reason,
                "ip_address": ip_address,
            },
            ensure_ascii=False,
            default=str,
        ),
    )
