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
from app.services import project_report_service as service


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


@pytest.mark.parametrize("contains_macro", [False, True])
def test_docx_container_validation(storage, database, contains_macro):
    buffer = BytesIO()
    with ZipFile(buffer, "w") as document:
        document.writestr("[Content_Types].xml", "<Types/>")
        document.writestr("word/document.xml", "<document/>")
        if contains_macro:
            document.writestr("word/vbaProject.bin", b"macro")
    if contains_macro:
        with pytest.raises(BusinessException):
            service.upload_report(database, 10, upload("报告.docx", buffer.getvalue()), USER)
        database.commit.assert_not_called()
    else:
        result = service.upload_report(database, 10, upload("报告.docx", buffer.getvalue()), USER)
        assert result["filename"] == "报告.docx"


def test_io_failure_reports_a_clear_message_and_keeps_draft(storage, database, monkeypatch):
    monkeypatch.setattr(service.os, "replace", MagicMock(side_effect=PermissionError("denied")))
    with pytest.raises(BusinessException) as error:
        service.upload_report(database, 10, upload(), USER)
    assert error.value.status_code == 503
    assert "项目草稿已保留" in error.value.message
    assert list((storage / "10").iterdir()) == []
