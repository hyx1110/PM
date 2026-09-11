from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.responses import success
from app.models.user import User
from app.services import import_export_service

router = APIRouter(prefix="/data-exchange", tags=["数据交换"])


def _excel_response(content: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/templates/{resource_type}")
def download_template(
    resource_type: str,
    _: User = Depends(require_permission("import:manage")),
):
    return _excel_response(import_export_service.create_template(resource_type), f"{resource_type}_import_template.xlsx")


@router.post("/imports/{resource_type}")
async def import_data(
    resource_type: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission("import:manage")),
    db: Session = Depends(get_db),
):
    content = await file.read()
    item = import_export_service.import_workbook(
        db, resource_type, file.filename or "upload.xlsx", content, current_user
    )
    return success(item)


@router.get("/imports")
def import_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    resource_type: str | None = None,
    _: User = Depends(require_permission("import:manage")),
    db: Session = Depends(get_db),
):
    return success(import_export_service.list_import_jobs(db, page, page_size, resource_type))


@router.get("/exports/schedules")
def export_schedules(
    start_date: date,
    end_date: date,
    current_user: User = Depends(require_permission("export:download")),
    db: Session = Depends(get_db),
):
    return _excel_response(
        import_export_service.export_schedules(db, current_user, start_date, end_date),
        f"schedules_{start_date}_{end_date}.xlsx",
    )


@router.get("/exports/executions")
def export_executions(
    start_date: date,
    end_date: date,
    current_user: User = Depends(require_permission("export:download")),
    db: Session = Depends(get_db),
):
    return _excel_response(
        import_export_service.export_executions(db, current_user, start_date, end_date),
        f"executions_{start_date}_{end_date}.xlsx",
    )


@router.get("/exports/process-report")
def export_process_report(
    start_date: date,
    end_date: date,
    current_user: User = Depends(require_permission("export:download")),
    db: Session = Depends(get_db),
):
    return _excel_response(
        import_export_service.export_process_report(db, current_user, start_date, end_date),
        f"process_report_{start_date}_{end_date}.xlsx",
    )

