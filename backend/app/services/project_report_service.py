"""Private, per-project initiation report storage (no public static URLs)."""
import logging
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BusinessException, bad_request, not_found
from app.models.project import Project
from app.models.project_report import ProjectInitiationReport
from app.models.user import User
from app.services import project_service
from app.services.operation_log_service import log_operation

logger = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[2]
MAX_REPORT_BYTES = 20 * 1024 * 1024
MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _storage_root() -> Path:
    configured = Path(settings.project_files_dir)
    return (configured if configured.is_absolute() else BACKEND_DIR / configured).resolve()


def _project_directory(project_id: int) -> Path:
    root = _storage_root()
    directory = (root / str(project_id)).resolve()
    if project_id <= 0 or not directory.is_relative_to(root):
        raise bad_request("项目附件目录无效，请联系管理员")
    return directory


def _stored_path(project_id: int, storage_name: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}\.(pdf|doc|docx)", storage_name):
        raise bad_request("项目附件存储信息无效，请联系管理员")
    directory = _project_directory(project_id)
    path = (directory / storage_name).resolve()
    if not path.is_relative_to(directory):
        raise bad_request("项目附件存储路径无效，请联系管理员")
    return path


def _validated_filename(filename: str | None) -> tuple[str, str]:
    # Client names are display/download metadata only, never server paths.
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name or len(name) > 255 or any(unicodedata.category(char).startswith("C") for char in name):
        raise bad_request("附件文件名无效，文件名不能超过 255 个字符或包含控制字符")
    extension = Path(name).suffix.lower()
    if extension not in MEDIA_TYPES:
        raise bad_request("立项报告仅支持 PDF、DOC、DOCX 文件")
    return name, extension


def _validate_document(path: Path, extension: str) -> None:
    with path.open("rb") as source:
        signature = source.read(8)
    valid = False
    if extension == ".pdf":
        valid = signature.startswith(b"%PDF-")
    elif extension == ".doc":
        valid = signature == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    elif extension == ".docx":
        try:
            with ZipFile(path) as archive:
                entries = set(archive.namelist())
                valid = {"[Content_Types].xml", "word/document.xml"}.issubset(entries)
                valid = valid and not any(name.lower().endswith("vbaproject.bin") for name in entries)
        except BadZipFile:
            valid = False
    if not valid:
        raise bad_request("文件内容与报告格式不匹配，请上传有效的 PDF 或 Word 文档（DOCX 不允许含宏）")


def report_metadata(report: ProjectInitiationReport | None) -> dict | None:
    if report is None:
        return None
    return {
        "project_id": report.project_id,
        "filename": report.original_filename,
        "size_bytes": report.size_bytes,
        "uploaded_by": report.uploaded_by,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }


def get_report(db: Session, project_id: int, user: User) -> dict | None:
    project_service.assert_project_visible(db, project_id, user)
    return report_metadata(db.get(ProjectInitiationReport, project_id))


def _assert_report_editable(db: Session, project_id: int, user: User) -> Project:
    # Same project-row lock as submit/approve: a report cannot change mid-approval.
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.is_deleted.is_(False))
        .with_for_update().execution_options(populate_existing=True)
    )
    if project is None:
        raise not_found("项目不存在或已删除")
    project_service.assert_project_manageable(db, project_id, user)
    if project.approval_status not in {"draft", "rejected"} or project.status == "completed":
        raise bad_request("仅草稿或已驳回项目可以上传或更换立项报告；待审批及已审批项目的报告已锁定")
    return project


def _cleanup_failed_file(path: Path | None) -> None:
    if path is not None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Failed to clean uncommitted project report: %s", path)


def upload_report(db: Session, project_id: int, upload: UploadFile, user: User) -> dict:
    temporary_path: Path | None = None
    saved_path: Path | None = None
    committed = False
    try:
        _assert_report_editable(db, project_id, user)
        name, extension = _validated_filename(upload.filename)
        if upload.size is not None and upload.size > MAX_REPORT_BYTES:
            raise bad_request("立项报告不能超过 20 MB")
        directory = _project_directory(project_id)
        directory.mkdir(parents=True, exist_ok=True)
        storage_name = f"{uuid4().hex}{extension}"
        size = 0
        upload.file.seek(0)
        # Bounded reads; never load the entire attachment in application memory.
        with tempfile.NamedTemporaryFile(mode="wb", dir=directory, prefix=".report-", suffix=".part", delete=False) as destination:
            temporary_path = Path(destination.name)
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_REPORT_BYTES:
                    raise bad_request("立项报告不能超过 20 MB")
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        if size == 0:
            raise bad_request("立项报告不能为空文件")
        _validate_document(temporary_path, extension)
        saved_path = _stored_path(project_id, storage_name)
        os.replace(temporary_path, saved_path)
        temporary_path = None

        # Use a current read after the project lock. Permission lookups may have
        # already established an older MySQL REPEATABLE READ snapshot.
        report = db.get(ProjectInitiationReport, project_id, with_for_update=True, populate_existing=True)
        before = report_metadata(report)
        if report is None:
            report = ProjectInitiationReport(project_id=project_id)
            db.add(report)
        report.original_filename = name
        report.storage_name = storage_name
        report.media_type = MEDIA_TYPES[extension]
        report.size_bytes = size
        report.uploaded_by = user.id
        db.flush()
        result = report_metadata(report)
        log_operation(
            db, operator_id=user.id, module="project", action="update" if before else "create",
            object_type="project_initiation_report", object_id=project_id,
            before_data=before, after_data=result,
        )
        db.commit()
        committed = True
        # Retain replaced reports for recovery/audit and in-flight downloads.
        # Only this metadata row identifies the current report visible in the UI.
        return result
    except OSError as exc:
        db.rollback()
        logger.exception("Unable to save initiation report for project %s", project_id)
        raise BusinessException(503, 50321, "立项报告保存失败，请联系管理员检查服务器附件目录权限及磁盘空间；项目草稿已保留") from exc
    except Exception:
        db.rollback()
        raise
    finally:
        try:
            upload.file.close()
        except OSError:
            logger.warning("Unable to close temporary upload stream", exc_info=True)
        _cleanup_failed_file(temporary_path)
        if not committed:
            _cleanup_failed_file(saved_path)


def report_download(db: Session, project_id: int, user: User) -> tuple[Path, str, str]:
    project_service.assert_project_visible(db, project_id, user)
    report = db.get(ProjectInitiationReport, project_id)
    if report is None:
        raise not_found("该项目尚未上传立项报告")
    path = _stored_path(project_id, report.storage_name)
    if not path.is_file():
        raise not_found("立项报告文件不存在，请联系管理员检查附件存储或恢复备份")
    return path, report.original_filename, report.media_type
