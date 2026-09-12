from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from typing import Any, Callable
from zipfile import BadZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_role_codes
from app.core.exceptions import bad_request
from app.core.security import hash_password
from app.models.execution import ExecutionRecord
from app.models.import_job import ImportJob
from app.models.organization import Department, Organization
from app.models.project import Project
from app.models.rbac import Role, UserRole
from app.models.schedule import ScheduleBooking
from app.models.task import Task
from app.models.user import User
from app.schemas.project import ProjectCreate
from app.schemas.task import TaskCreate
from app.schemas.user import UserCreate
from app.services.operation_log_service import log_operation
from app.services.notification_service import create_notification
from app.services.project_service import visible_project_ids

RESOURCE_HEADERS = {
    "users": [
        ("username", "用户名*"),
        ("name", "姓名*"),
        ("password", "初始密码"),
        ("email", "邮箱"),
        ("phone", "手机"),
        ("department_code", "部门编码"),
        ("organization_code", "组织编码"),
        ("supervisor_username", "主管用户名"),
        ("role_codes", "角色编码(逗号分隔)"),
        ("status", "状态"),
    ],
    "projects": [
        ("code", "项目编号*"),
        ("name", "项目名称*"),
        ("project_type", "项目类型"),
        ("manager_username", "项目经理用户名*"),
        ("department_code", "部门编码*"),
        ("budget_hours", "项目总工时*"),
        ("planned_start", "计划开始*"),
        ("planned_end", "计划结束*"),
        ("priority", "优先级"),
        ("description", "描述"),
        ("remark", "备注"),
    ],
    "tasks": [
        ("project_code", "项目编号*"),
        ("parent_task_name", "上级任务名称"),
        ("name", "任务名称*"),
        ("task_type", "任务类型"),
        ("owner_username", "负责人用户名*"),
        ("planned_start", "计划开始*"),
        ("planned_end", "计划结束*"),
        ("estimated_hours", "预计工时"),
        ("status", "状态"),
        ("priority", "优先级"),
        ("description", "描述"),
        ("remark", "备注"),
    ],
}

EXAMPLES = {
    "users": ["zhangsan", "张三", "", "zhangsan@example.com", "13800000000", "", "", "", "project_member", "active"],
    "projects": ["P-2026-001", "示例项目", "General", "zhangsan", "D001", 160, date(2026, 10, 1), date(2026, 12, 31), "high", "", ""],
    "tasks": ["P-2026-001", "", "需求分析", "Project", "admin", datetime(2026, 10, 1, 9), datetime(2026, 10, 3, 18), 24, "not_started", "high", "", ""],
}


def _style_sheet(sheet, widths: list[int]) -> None:
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    header_fill = PatternFill("solid", fgColor="355F8D")
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    sheet.row_dimensions[1].height = 24
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[chr(64 + index)].width = width


def _add_list_validation(book: Workbook, sheet, column: int, values: list[str]) -> None:
    lists = book["_lists"] if "_lists" in book.sheetnames else book.create_sheet("_lists")
    target_column = lists.max_column + 1 if lists.cell(1, 1).value else 1
    for row, value in enumerate(values, 1):
        lists.cell(row, target_column, value)
    column_letter = chr(64 + target_column)
    validation = DataValidation(
        type="list",
        formula1=f"'_lists'!${column_letter}$1:${column_letter}${len(values)}",
        allow_blank=True,
    )
    sheet.add_data_validation(validation)
    validation.add(f"{chr(64 + column)}2:{chr(64 + column)}5000")
    lists.sheet_state = "veryHidden"


def create_template(resource_type: str) -> bytes:
    headers = RESOURCE_HEADERS.get(resource_type)
    if not headers:
        raise bad_request("unsupported import resource")
    book = Workbook()
    sheet = book.active
    sheet.title = "导入数据"
    sheet.append([label for _, label in headers])
    sheet.append(EXAMPLES[resource_type])
    _style_sheet(sheet, [20] * len(headers))
    date_fields = {"planned_start", "planned_end"}
    for index, (field, _) in enumerate(headers, 1):
        if field in date_fields:
            sheet.cell(2, index).number_format = "yyyy-mm-dd hh:mm"
    field_index = {field: index + 1 for index, (field, _) in enumerate(headers)}
    if "status" in field_index:
        status_values = {
            "users": ["active", "disabled"],
            "projects": ["Draft", "Planned", "Running", "Suspended", "Completed", "Cancelled"],
            "tasks": ["not_started", "pending", "confirmed", "running", "completed", "delayed", "cancelled"],
        }[resource_type]
        _add_list_validation(book, sheet, field_index["status"], status_values)
    if "priority" in field_index:
        _add_list_validation(book, sheet, field_index["priority"], ["low", "medium", "high", "critical"])
    if "task_type" in field_index:
        _add_list_validation(book, sheet, field_index["task_type"], ["Project", "Routine", "Training", "Leave", "Other"])
    notes = book.create_sheet("填写说明", 1)
    notes.append(["规则", "说明"])
    notes.append(["必填字段", "标题包含 * 的列必须填写；请勿修改标题行。"])
    notes.append(["日期", "请使用 Excel 日期/时间单元格或 YYYY-MM-DD HH:mm 格式。"])
    notes.append(["数字", "工时等数值请使用真实数字单元格，不要添加单位。"])
    notes.append(["导入策略", "按行校验并导入；失败行会保留错误明细，成功行不会被回滚。"])
    _style_sheet(notes, [20, 76])
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


def _clean(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


def _to_datetime(value: Any, field: str) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    if isinstance(value, str):
        text = value.strip()
        for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, pattern)
            except ValueError:
                continue
    raise ValueError(f"{field} 必须是有效日期时间")


def _to_date(value: Any, field: str) -> date:
    return _to_datetime(value, field).date()


def _lookup(db: Session, model, column, value: Any, message: str):
    if value in (None, ""):
        return None
    statement = select(model).where(column == value)
    if model is User:
        statement = statement.where(User.is_deleted.is_(False))
    item = db.scalar(statement)
    if not item:
        raise ValueError(message)
    return item


def _required_lookup(db: Session, model, column, value: Any, message: str):
    if value in (None, ""):
        raise ValueError(message)
    item = _lookup(db, model, column, value, message)
    if not item:
        raise ValueError(message)
    return item


def _import_user(db: Session, row: dict[str, Any], operator: User) -> User:
    department = _lookup(db, Department, Department.code, row.get("department_code"), "部门编码不存在")
    organization = None
    if row.get("organization_code"):
        if not department:
            raise ValueError("填写组织编码时必须同时填写部门编码")
        organization_filters = [Organization.code == row["organization_code"]]
        if department:
            organization_filters.append(Organization.department_id == department.id)
        organization = db.scalar(select(Organization).where(*organization_filters).limit(1))
        if not organization:
            raise ValueError("组织编码不存在或不属于所选部门")
    supervisor = _lookup(db, User, User.username, row.get("supervisor_username"), "主管用户名不存在")
    role_codes = [item.strip() for item in str(row.get("role_codes") or "").split(",") if item.strip()]
    roles = db.scalars(select(Role).where(Role.code.in_(role_codes))).all() if role_codes else []
    missing_roles = set(role_codes) - {role.code for role in roles}
    if missing_roles:
        raise ValueError(f"角色编码不存在：{', '.join(sorted(missing_roles))}")
    payload = UserCreate(
        username=row.get("username"),
        name=row.get("name"),
        password=row.get("password") or settings.import_default_password,
        email=row.get("email") or None,
        phone=str(row["phone"]) if row.get("phone") not in (None, "") else None,
        department_id=department.id if department else None,
        organization_id=organization.id if organization else None,
        supervisor_id=supervisor.id if supervisor else None,
        status=row.get("status") or "active",
    )
    if payload.status not in {"active", "disabled"}:
        raise ValueError("用户状态必须是 active 或 disabled")
    if db.scalar(select(User.id).where(User.username == payload.username)):
        raise ValueError("用户名已存在")
    item = User(**payload.model_dump(exclude={"password", "role_ids"}), password_hash=hash_password(payload.password))
    db.add(item)
    db.flush()
    db.add_all([UserRole(user_id=item.id, role_id=role.id) for role in roles])
    return item


def _import_project(db: Session, row: dict[str, Any], operator: User) -> Project:
    manager = _required_lookup(db, User, User.username, row.get("manager_username"), "项目经理用户名不能为空且必须存在")
    department = _required_lookup(db, Department, Department.code, row.get("department_code"), "部门编码不能为空且必须存在")
    if manager.id != operator.id or "project_manager" not in get_role_codes(db, operator.id):
        raise ValueError("项目只能由项目经理本人导入，项目经理用户名必须是当前用户")
    if manager.department_id != department.id:
        raise ValueError("项目经理必须属于项目所属部门")
    if not department.manager_id:
        raise ValueError("请先为项目所属部门设置 L3（部门主管）")
    l3 = db.get(User, department.manager_id)
    if (
        not l3
        or l3.is_deleted
        or l3.status != "active"
        or l3.department_id != department.id
        or "department_manager" not in get_role_codes(db, l3.id)
    ):
        raise ValueError("部门负责人必须是有效的 L3（部门主管）用户")
    payload = ProjectCreate(
        code=row.get("code"),
        name=row.get("name"),
        project_type=row.get("project_type") or "General",
        manager_id=manager.id,
        department_id=department.id,
        budget_hours=Decimal(str(row.get("budget_hours") or 0)),
        status="Draft",
        planned_start=_to_date(row.get("planned_start"), "计划开始"),
        planned_end=_to_date(row.get("planned_end"), "计划结束"),
        priority=row.get("priority") or "medium",
        description=row.get("description") or None,
        remark=row.get("remark") or None,
    )
    if db.scalar(select(Project.id).where(Project.code == payload.code)):
        raise ValueError("项目编号已存在")
    item = Project(
        **payload.model_dump(exclude={"status"}),
        status="Draft",
        approval_status="pending",
        created_by=operator.id,
    )
    db.add(item)
    db.flush()
    create_notification(
        db,
        l3.id,
        "project_approval_required",
        "导入项目待 L3 审批",
        f"项目 {item.code} - {item.name} 已导入，请审核项目与 {item.budget_hours} 小时工时额度。",
        level="warning",
        related_type="project",
        related_id=item.id,
    )
    return item


def _import_task(db: Session, row: dict[str, Any], operator: User) -> Task:
    project = _required_lookup(db, Project, Project.code, row.get("project_code"), "项目编号不能为空且必须存在")
    if project.approval_status != "approved":
        raise ValueError("项目尚未通过 L3 审批，不能导入任务")
    owner = _required_lookup(db, User, User.username, row.get("owner_username"), "负责人用户名不能为空且必须存在")
    parent = None
    if row.get("parent_task_name"):
        parent = db.scalar(
            select(Task).where(Task.project_id == project.id, Task.name == row["parent_task_name"])
        )
        if not parent:
            raise ValueError("上级任务名称不存在")
        if parent.parent_id is not None:
            raise ValueError("系统只支持两级任务，上级任务不能是二级任务")
    payload = TaskCreate(
        project_id=project.id,
        parent_id=parent.id if parent else None,
        name=row.get("name"),
        task_type=row.get("task_type") or "Project",
        owner_id=owner.id,
        planned_start=_to_datetime(row.get("planned_start"), "计划开始"),
        planned_end=_to_datetime(row.get("planned_end"), "计划结束"),
        estimated_hours=Decimal(str(row.get("estimated_hours") or 0)),
        status=row.get("status") or "not_started",
        priority=row.get("priority") or "medium",
        description=row.get("description") or None,
        remark=row.get("remark") or None,
    )
    item = Task(**payload.model_dump())
    db.add(item)
    db.flush()
    return item


IMPORT_HANDLERS: dict[str, Callable[[Session, dict[str, Any], User], Any]] = {
    "users": _import_user,
    "projects": _import_project,
    "tasks": _import_task,
}


def _assert_import_scope(
    db: Session, resource_type: str, row: dict[str, Any], operator: User
) -> None:
    roles = get_role_codes(db, operator.id)
    if "super_admin" in roles:
        return
    if resource_type in {"users", "projects"}:
        department_code = row.get("department_code")
        department_id = db.scalar(
            select(Department.id).where(Department.code == department_code)
        ) if department_code else None
        if not operator.department_id or department_id != operator.department_id:
            raise ValueError("只能导入到当前操作人所属部门")
    if resource_type == "tasks":
        project_id = db.scalar(select(Project.id).where(Project.code == row.get("project_code")))
        manageable = visible_project_ids(db, operator)
        if not project_id or manageable is not None and project_id not in manageable:
            raise ValueError("任务所属项目不在当前操作人的数据范围内")


def import_workbook(
    db: Session, resource_type: str, filename: str, content: bytes, operator: User
) -> ImportJob:
    headers = RESOURCE_HEADERS.get(resource_type)
    handler = IMPORT_HANDLERS.get(resource_type)
    if not headers or not handler:
        raise bad_request("unsupported import resource")
    if not filename.lower().endswith(".xlsx"):
        raise bad_request("only .xlsx files are supported")
    if len(content) > settings.import_max_mb * 1024 * 1024:
        raise bad_request(f"file exceeds {settings.import_max_mb} MB")
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except (OSError, ValueError, KeyError, BadZipFile, InvalidFileException) as exc:
        raise bad_request("invalid Excel workbook") from exc
    if "导入数据" not in workbook.sheetnames:
        raise bad_request("workbook is missing sheet: 导入数据")
    sheet = workbook["导入数据"]
    expected_labels = [label for _, label in headers]
    actual_labels = [cell.value for cell in sheet[1]][: len(expected_labels)]
    if actual_labels != expected_labels:
        raise bad_request("Excel headers do not match the selected template")
    job = ImportJob(
        resource_type=resource_type,
        original_filename=filename[:255],
        operator_id=operator.id,
        status="processing",
    )
    db.add(job)
    db.flush()
    errors: list[dict] = []
    success_rows = 0
    failed_rows = 0
    total_rows = 0
    field_names = [field for field, _ in headers]
    for row_number, values in enumerate(sheet.iter_rows(min_row=2, values_only=True), 2):
        if not any(value not in (None, "") for value in values):
            continue
        total_rows += 1
        row = {field: _clean(values[index]) if index < len(values) else None for index, field in enumerate(field_names)}
        try:
            with db.begin_nested():
                _assert_import_scope(db, resource_type, row, operator)
                handler(db, row, operator)
            success_rows += 1
        except ValidationError as exc:
            failed_rows += 1
            first = exc.errors()[0]
            if len(errors) < 500:
                errors.append({"row": row_number, "field": ".".join(map(str, first["loc"])), "message": first["msg"]})
        except (ValueError, TypeError, IntegrityError) as exc:
            failed_rows += 1
            if len(errors) < 500:
                errors.append({"row": row_number, "field": None, "message": str(exc)[:500]})
    if failed_rows > 500:
        errors[-1] = {
            "row": 0,
            "field": None,
            "message": f"另有 {failed_rows - 499} 条错误未展示；导入仍已处理全部数据行",
        }
    job.total_rows = total_rows
    job.success_rows = success_rows
    job.failed_rows = failed_rows
    job.errors = errors
    job.status = "completed" if not failed_rows else ("partial" if success_rows else "failed")
    log_operation(
        db,
        operator_id=operator.id,
        module="data_exchange",
        action="import",
        object_type="import_job",
        object_id=job.id,
        after_data={
            "resource_type": resource_type,
            "filename": filename,
            "total_rows": total_rows,
            "success_rows": success_rows,
            "failed_rows": failed_rows,
        },
    )
    db.commit()
    db.refresh(job)
    return job


def list_import_jobs(db: Session, page: int, page_size: int, resource_type: str | None) -> dict:
    filters = [ImportJob.resource_type == resource_type] if resource_type else []
    total = db.scalar(select(func.count(ImportJob.id)).where(*filters)) or 0
    rows = db.execute(
        select(ImportJob, User.name.label("operator_name"))
        .join(User, User.id == ImportJob.operator_id)
        .where(*filters)
        .order_by(ImportJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = []
    for item, operator_name in rows:
        data = {column.name: getattr(item, column.name) for column in ImportJob.__table__.columns}
        data["operator_name"] = operator_name
        items.append(data)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _export_book(title: str, headers: list[str], rows: list[list[Any]], date_columns: set[int]) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = title[:31]
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    _style_sheet(sheet, [18] * len(headers))
    for row in sheet.iter_rows(min_row=2):
        for index in date_columns:
            row[index - 1].number_format = "yyyy-mm-dd hh:mm"
    summary = book.create_sheet("导出说明")
    summary.append(["项目", "内容"])
    summary.append(["报表", title])
    summary.append(["生成时间", datetime.now()])
    summary["B3"].number_format = "yyyy-mm-dd hh:mm:ss"
    summary.append(["数据行数", len(rows)])
    _style_sheet(summary, [18, 32])
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


def _validate_export_range(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise bad_request("end_date must be on or after start_date")
    if (end_date - start_date).days > 366:
        raise bad_request("export range cannot exceed 366 days")


def export_schedules(db: Session, user: User, start_date: date, end_date: date) -> bytes:
    _validate_export_range(start_date, end_date)
    scope = visible_project_ids(db, user)
    filters = [
        ScheduleBooking.end_time > datetime.combine(start_date, time.min),
        ScheduleBooking.start_time < datetime.combine(end_date + timedelta(days=1), time.min),
    ]
    if scope is not None:
        filters.append(ScheduleBooking.project_id.in_(scope or {-1}))
    rows = db.execute(
        select(ScheduleBooking, User.name, Project.code, Project.name, Task.name)
        .join(User, User.id == ScheduleBooking.user_id)
        .join(Project, Project.id == ScheduleBooking.project_id)
        .join(Task, Task.id == ScheduleBooking.task_id)
        .where(*filters)
        .order_by(ScheduleBooking.start_time, User.name)
    ).all()
    values = [
        [item.id, user_name, code, project_name, task_name, item.start_time, item.end_time, float(item.planned_hours), item.status, item.remark]
        for item, user_name, code, project_name, task_name in rows
    ]
    return _export_book("排期明细", ["预约ID", "人员", "项目编号", "项目", "任务", "开始", "结束", "计划工时", "状态", "备注"], values, {6, 7})


def export_executions(db: Session, user: User, start_date: date, end_date: date) -> bytes:
    _validate_export_range(start_date, end_date)
    scope = visible_project_ids(db, user)
    filters = [
        ExecutionRecord.actual_start >= datetime.combine(start_date, time.min),
        ExecutionRecord.actual_start < datetime.combine(end_date + timedelta(days=1), time.min),
    ]
    if scope is not None:
        filters.append(Task.project_id.in_(scope or {-1}))
    rows = db.execute(
        select(ExecutionRecord, User.name, Project.code, Project.name, Task.name)
        .join(User, User.id == ExecutionRecord.user_id)
        .join(Task, Task.id == ExecutionRecord.task_id)
        .join(Project, Project.id == Task.project_id)
        .where(*filters)
        .order_by(ExecutionRecord.actual_start)
    ).all()
    values = [
        [item.id, user_name, code, project_name, task_name, item.actual_start, item.actual_end, float(item.actual_hours), item.status, item.description, item.exception_reason]
        for item, user_name, code, project_name, task_name in rows
    ]
    return _export_book("执行明细", ["执行ID", "人员", "项目编号", "项目", "任务", "实际开始", "实际结束", "实际工时", "状态", "执行说明", "异常原因"], values, {6, 7})


def export_process_report(db: Session, user: User, start_date: date, end_date: date) -> bytes:
    _validate_export_range(start_date, end_date)
    from app.services.report_service import process_report

    report = process_report(
        db, user, 1, 100000, start_date=start_date, end_date=end_date, project_id=None, owner_id=None
    )
    values = [
        [
            item["project_name"], item.get("level1_task"), item.get("level2_task"), item["owner_name"],
            item["planned_start"], item["planned_end"], item.get("actual_start"), item.get("actual_end"),
            float(item["estimated_hours"] or 0), float(item["actual_hours"] or 0),
            float(item["achievement_rate"]) if item.get("achievement_rate") is not None else None,
            float(item["achievement_quality"]) if item.get("achievement_quality") is not None else None,
            item["effective_status"],
        ]
        for item in report["items"]
    ]
    return _export_book("项目过程报表", ["项目", "一级任务", "二级任务", "负责人", "计划开始", "计划结束", "实际开始", "实际结束", "预计工时", "实际工时", "达成率", "达成质量", "状态"], values, {5, 6, 7, 8})
