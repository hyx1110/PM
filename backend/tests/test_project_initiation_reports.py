"""Report upload regressions. Source only; run manually, no real DB/server needed."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock
from zipfile import ZipFile

from fastapi import UploadFile
import pytest

from app.core.exceptions import BusinessException, forbidden
from app.models.project import Project
from app.models.project_report import ProjectInitiationReport
from app.schemas.project import ProjectCreate
from app.services import project_report_service as service
from app.services import import_export_service


PDF = b"%PDF-1.4\nreport fixture\n%%EOF"
USER = SimpleNamespace(id=7)


def upload(filename="立项报告.pdf", content=PDF, size=None):
    return UploadFile(file=BytesIO(content), filename=filename, size=size)


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(service.settings, "project_files_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def database(monkeypatch):
    db = MagicMock()
    db.scalar.return_value = Project(id=10, approval_status="draft", status="not_started", is_deleted=False)
    db.get.return_value = None
    monkeypatch.setattr(service.project_service, "assert_project_manageable", MagicMock())
    monkeypatch.setattr(service.project_service, "assert_project_visible", MagicMock())
    monkeypatch.setattr(service, "log_operation", MagicMock())
    return db


def test_relative_directory_is_anchored_to_backend_not_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(service.settings, "project_files_dir", "storage/projects")
    assert service._storage_root() == service.BACKEND_DIR / "storage" / "projects"


def test_upload_uses_project_directory_generated_name_and_private_metadata(storage, database):
    item = upload(filename="../../立项报告.PDF")
    result = service.upload_report(database, 10, item, USER)
    files = list((storage / "10").iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".pdf"
    assert len(files[0].stem) == 32
    assert files[0].read_bytes() == PDF
    assert result["filename"] == "立项报告.PDF"
    assert result["size_bytes"] == len(PDF)
    assert "storage_name" not in result and "path" not in result
    assert item.file.closed
    database.get.assert_called_with(ProjectInitiationReport, 10, with_for_update=True, populate_existing=True)
    database.commit.assert_called_once()


@pytest.mark.parametrize("filename,content", [
    ("report.exe", PDF), ("report.pdf.exe", PDF), ("report.pdf", b"<html>fake</html>"),
    ("report.doc", PDF), ("report.docx", b"not a zip"), ("report.pdf", b""),
    ("bad\r\nname.pdf", PDF), ("x" * 256 + ".pdf", PDF),
])
def test_invalid_file_rolls_back_and_removes_partial_files(storage, database, filename, content):
    with pytest.raises(BusinessException) as error:
        service.upload_report(database, 10, upload(filename, content), USER)
    assert error.value.status_code == 400
    assert not list(storage.rglob("*.part"))
    assert not list(storage.rglob("*.pdf"))
    database.commit.assert_not_called()
    database.rollback.assert_called_once()


@pytest.mark.parametrize("reported_size", [None, 1, len(PDF)])
def test_size_limit_is_enforced_even_without_or_with_false_client_size(storage, database, monkeypatch, reported_size):
    monkeypatch.setattr(service, "MAX_REPORT_BYTES", 8)
    with pytest.raises(BusinessException):
        service.upload_report(database, 10, upload(size=reported_size), USER)
    assert not list(storage.rglob("*.part"))
    database.commit.assert_not_called()


def test_failed_database_commit_removes_new_file(storage, database):
    database.commit.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError):
        service.upload_report(database, 10, upload(), USER)
    assert list((storage / "10").iterdir()) == []
    database.rollback.assert_called_once()


def test_replacing_draft_report_retains_previous_file(storage, database):
    directory = storage / "10"
    directory.mkdir()
    old = directory / ("a" * 32 + ".pdf")
    old.write_bytes(PDF)
    report = ProjectInitiationReport(project_id=10, storage_name=old.name, original_filename="旧报告.pdf",
                                     size_bytes=len(PDF), uploaded_by=7, media_type="application/pdf")
    database.get.return_value = report
    result = service.upload_report(database, 10, upload("新报告.pdf"), USER)
    assert result["filename"] == "新报告.pdf"
    assert report.storage_name != old.name
    assert old.read_bytes() == PDF
    assert len(list(directory.glob("*.pdf"))) == 2


@pytest.mark.parametrize("state", ["pending", "approved"])
def test_reports_are_frozen_after_submission(storage, database, state):
    database.scalar.return_value.approval_status = state
    with pytest.raises(BusinessException):
        service.upload_report(database, 10, upload(), USER)
    assert list(storage.iterdir()) == []
    database.commit.assert_not_called()


def test_missing_or_deleted_project_cannot_receive_attachment(storage, database):
    database.scalar.return_value = None
    with pytest.raises(BusinessException) as error:
        service.upload_report(database, 10, upload(), USER)
    assert error.value.status_code == 404
    assert list(storage.iterdir()) == []


def test_member_cannot_upload_without_management_rights(storage, database, monkeypatch):
    monkeypatch.setattr(service.project_service, "assert_project_manageable", MagicMock(side_effect=forbidden()))
    with pytest.raises(BusinessException) as error:
        service.upload_report(database, 10, upload(), USER)
    assert error.value.status_code == 403
    assert list(storage.iterdir()) == []


@pytest.mark.parametrize("reader", [service.get_report, service.report_download])
def test_metadata_and_download_cannot_bypass_project_visibility(database, monkeypatch, reader):
    monkeypatch.setattr(service.project_service, "assert_project_visible", MagicMock(side_effect=forbidden()))
    with pytest.raises(BusinessException) as error:
        reader(database, 10, USER)
    assert error.value.status_code == 403
    database.get.assert_not_called()


def test_legacy_project_without_report_has_empty_metadata(database):
    assert service.get_report(database, 10, USER) is None
    with pytest.raises(BusinessException) as error:
        service.report_download(database, 10, USER)
    assert error.value.status_code == 404


def test_missing_server_file_is_a_clear_404(storage, database):
    database.get.return_value = ProjectInitiationReport(project_id=10, storage_name="a" * 32 + ".pdf")
    with pytest.raises(BusinessException) as error:
        service.report_download(database, 10, USER)
    assert error.value.status_code == 404
    assert "备份" in error.value.message


def test_invalid_stored_path_is_rejected(storage):
    with pytest.raises(BusinessException):
        service._stored_path(10, "../../secret.pdf")


@pytest.mark.parametrize("extension,main_part", [
    ("docx", "word/document.xml"), ("xlsx", "xl/workbook.xml"), ("pptx", "ppt/presentation.xml"),
])
@pytest.mark.parametrize("contains_macro", [False, True])
def test_office_container_validation(storage, database, extension, main_part, contains_macro):
    buffer = BytesIO()
    with ZipFile(buffer, "w") as document:
        document.writestr("[Content_Types].xml", "<Types/>")
        document.writestr(main_part, "<document/>")
        if contains_macro:
            document.writestr(main_part.split("/")[0] + "/vbaProject.bin", b"macro")
    if contains_macro:
        with pytest.raises(BusinessException):
            service.upload_report(database, 10, upload(f"报告.{extension}", buffer.getvalue()), USER)
        database.commit.assert_not_called()
    else:
        result = service.upload_report(database, 10, upload(f"报告.{extension}", buffer.getvalue()), USER)
        assert result["filename"] == f"报告.{extension}"
        files = list((storage / "10").iterdir())
        assert len(files) == 1 and files[0].suffix == f".{extension}"


def test_io_failure_reports_a_clear_message_and_keeps_draft(storage, database, monkeypatch):
    monkeypatch.setattr(service.os, "replace", MagicMock(side_effect=PermissionError("denied")))
    with pytest.raises(BusinessException) as error:
        service.upload_report(database, 10, upload(), USER)
    assert error.value.status_code == 503
    assert "项目草稿已保留" in error.value.message
    assert list((storage / "10").iterdir()) == []


@pytest.mark.parametrize("extension", ["doc", "xls", "ppt"])
def test_legacy_office_container_signature(storage, database, extension):
    # Minimal signature fixture; this check is not a complete Office parser.
    content = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"fixture"
    result = service.upload_report(database, 10, upload(f"report.{extension}", content), USER)
    assert result["filename"] == f"report.{extension}"
    report = database.add.call_args.args[0]
    assert report.media_type == service.MEDIA_TYPES[f".{extension}"]
    assert service._stored_path(10, report.storage_name).read_bytes() == content


@pytest.mark.parametrize("extension", ["xlsx", "pptx"])
def test_docx_renamed_to_other_office_format_is_rejected(storage, database, extension):
    buffer = BytesIO()
    with ZipFile(buffer, "w") as document:
        document.writestr("[Content_Types].xml", "<Types/>")
        document.writestr("word/document.xml", "<document/>")
    with pytest.raises(BusinessException):
        service.upload_report(database, 10, upload(f"report.{extension}", buffer.getvalue()), USER)
    database.commit.assert_not_called()
    assert not list(storage.rglob(f"*.{extension}"))


@pytest.mark.parametrize("extension", ["docm", "xlsm", "pptm", "exe", "zip"])
def test_unapproved_extensions_are_rejected(extension):
    with pytest.raises(BusinessException):
        service._validated_filename(f"report.{extension}")


def project_payload():
    return ProjectCreate(name="必传报告项目", manager_id=7, department_id=1, member_ids=[8],
                         budget_hours=8, planned_start="2026-10-09", planned_end="2026-10-10")


def test_new_project_requires_file_even_when_called_without_http(database):
    with pytest.raises(BusinessException) as error:
        service.project_service.create_project(database, project_payload(), USER)
    assert "必须上传" in error.value.message
    database.add.assert_not_called()
    database.commit.assert_not_called()


@pytest.mark.parametrize("content,valid", [(PDF, True), (b"fake pdf", False)])
def test_new_project_and_report_share_one_commit(storage, database, monkeypatch, content, valid):
    project_service = service.project_service
    monkeypatch.setattr(project_service, "get_role_codes", lambda *args: {"project_manager"})
    monkeypatch.setattr(project_service, "_validate_project_manager", lambda *args: USER)
    monkeypatch.setattr(project_service, "get_department_manager", lambda *args: SimpleNamespace(id=9))
    monkeypatch.setattr(project_service, "_validate_initial_project_members", lambda *args: [SimpleNamespace(id=8)])
    monkeypatch.setattr(project_service, "_add_initial_project_members", MagicMock())
    monkeypatch.setattr(project_service, "_generate_project_code", lambda *args: "P-REPORT-TEST")
    monkeypatch.setattr(project_service, "log_operation", MagicMock())

    def add(item):
        if isinstance(item, Project):
            item.id = 10
            database.scalar.return_value = item
    database.add.side_effect = add
    item = upload(content=content)
    if valid:
        project = project_service.create_project(database, project_payload(), USER, item)
        assert project.id == 10 and project.approval_status == "draft"
        database.commit.assert_called_once()
        database.rollback.assert_not_called()
        assert len(list(storage.rglob("*.pdf"))) == 1
    else:
        with pytest.raises(BusinessException):
            project_service.create_project(database, project_payload(), USER, item)
        database.commit.assert_not_called()
        database.rollback.assert_called()
        assert not list(storage.rglob("*.pdf"))
    assert item.file.closed


def test_submit_draft_without_report_is_blocked_before_notifications(database, monkeypatch):
    project = database.scalar.return_value
    project.manager_id, project.department_id = USER.id, 1
    monkeypatch.setattr(service.project_service, "get_role_codes", lambda *args: {"project_manager"})
    monkeypatch.setattr(service.project_service, "_validate_project_manager", MagicMock())
    notify = MagicMock()
    monkeypatch.setattr(service.project_service, "create_notification", notify)
    with pytest.raises(BusinessException) as error:
        service.project_service.submit_project(database, 10, USER)
    assert "必传" in error.value.message
    assert project.approval_status == "draft"
    notify.assert_not_called()
    database.commit.assert_not_called()


@pytest.mark.parametrize("stored_bytes", [None, b"", b"incorrect size", PDF])
def test_report_must_exist_on_server_before_submission(storage, database, stored_bytes):
    name = "a" * 32 + ".pdf"
    database.get.return_value = ProjectInitiationReport(project_id=10, storage_name=name, size_bytes=len(PDF))
    if stored_bytes is not None:
        directory = storage / "10"
        directory.mkdir()
        (directory / name).write_bytes(stored_bytes)
    if stored_bytes == PDF:
        service.assert_report_ready(database, 10)
    else:
        with pytest.raises(BusinessException):
            service.assert_report_ready(database, 10)
    database.get.assert_called_with(ProjectInitiationReport, 10, with_for_update=True, populate_existing=True)


def test_project_import_stays_draft_until_report_is_uploaded(monkeypatch):
    module = import_export_service
    db = MagicMock()
    manager = SimpleNamespace(id=7, employee_no="E7", department_id=1)
    department = SimpleNamespace(id=1, status="active")
    member = SimpleNamespace(id=8, employee_no="E8")
    db.scalars.return_value.all.return_value = [member]
    monkeypatch.setattr(module, "_required_lookup", lambda db, model, *args: manager if model is module.User else department)
    monkeypatch.setattr(module, "get_role_codes", lambda *args: {"project_manager"})
    monkeypatch.setattr(module, "has_global_project_access", lambda *args: False)
    monkeypatch.setattr(module, "_validate_project_manager", MagicMock())
    monkeypatch.setattr(module, "_validate_initial_project_members", MagicMock())
    monkeypatch.setattr(module, "_add_initial_project_members", MagicMock())
    monkeypatch.setattr(module, "get_department_manager", lambda *args: SimpleNamespace(id=9))
    monkeypatch.setattr(module, "_generate_project_code", lambda *args: "P-IMPORT-REPORT")
    notify = MagicMock()
    monkeypatch.setattr(module, "create_notification", notify)
    item = module._import_project(db, {
        "name": "导入草稿", "manager_employee_no": "E7", "department_code": "D1", "member_employee_nos": "E8",
        "budget_hours": 8, "planned_start": "2026-10-09", "planned_end": "2026-10-10",
    }, USER)
    assert item.approval_status == "draft" and item.approver_id is None
    notify.assert_not_called()
