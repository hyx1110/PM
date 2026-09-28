"""SMTP is fully mocked: these tests do not send any emails."""
import smtplib
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.notification import Notification
from app.services import email_service, notification_service


@pytest.fixture
def mail_settings(monkeypatch):
    settings = SimpleNamespace(smtp_enabled=True, smtp_host="smtp.example.invalid", smtp_port=587,
        smtp_from="notify@example.invalid", smtp_username="notify", smtp_password="not-a-real-password",
        smtp_use_tls=True, smtp_use_ssl=False, smtp_ca_file=None, smtp_timeout_seconds=10,
        smtp_max_attempts=3, smtp_subject_prefix="[项目协同] ", public_app_url="https://project.example.invalid")
    monkeypatch.setattr(email_service, "settings", settings)
    monkeypatch.setattr(notification_service, "settings", settings)
    return settings


def notification():
    return Notification(id=1, recipient_id=2, event_type="overtime_requested", title="加班申请", content="请审批",
        related_type="overtime", email_status="pending", email_attempts=0, delivered_channels=["in_app"])


def test_disabled_does_not_touch_smtp(monkeypatch, mail_settings):
    mail_settings.smtp_enabled = False
    smtp = MagicMock()
    monkeypatch.setattr(email_service.smtplib, "SMTP", smtp)
    assert email_service.send_email(SimpleNamespace(email="user@example.invalid"), notification()) is False
    smtp.assert_not_called()
    db = MagicMock()
    assert email_service.dispatch_email_pending(db)["attempted"] == 0
    db.scalar.assert_not_called()


@pytest.mark.parametrize("implicit_tls", [False, True])
def test_correct_tls_transport_and_stable_message_id(monkeypatch, mail_settings, implicit_tls):
    mail_settings.smtp_use_tls = not implicit_tls
    mail_settings.smtp_use_ssl = implicit_tls
    smtp, smtp_ssl = MagicMock(), MagicMock()
    monkeypatch.setattr(email_service.smtplib, "SMTP", smtp)
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", smtp_ssl)
    monkeypatch.setattr(email_service.ssl, "create_default_context", MagicMock())
    assert email_service.send_email(SimpleNamespace(email="user@example.invalid"), notification())
    chosen, other = (smtp_ssl, smtp) if implicit_tls else (smtp, smtp_ssl)
    other.assert_not_called()
    client = chosen.return_value.__enter__.return_value
    assert client.starttls.call_count == (0 if implicit_tls else 1)
    client.login.assert_called_once_with("notify", "not-a-real-password")
    message = client.send_message.call_args.args[0]
    assert message["Message-ID"] == "<notification-1@example.invalid>"
    assert "/executions?tab=overtime" in message.get_content()


def test_queue_is_saved_without_network(monkeypatch, mail_settings):
    db = MagicMock()
    db.get.return_value = SimpleNamespace(email="user@example.invalid")
    sender = MagicMock()
    monkeypatch.setattr(email_service, "send_email", sender)
    item = notification_service.create_notification(db, 2, "event", "标题", "正文")
    assert item.email_status == "pending"
    assert item.delivered_channels == ["in_app"]
    sender.assert_not_called()
    db.commit.assert_not_called()  # Business transaction owns the commit.


@pytest.mark.parametrize(("attempts", "expected"), [(0, "pending"), (2, "failed")])
def test_retry_backoff_and_limit(monkeypatch, mail_settings, attempts, expected):
    item = notification()
    item.email_attempts = attempts
    db = MagicMock()
    db.scalar.side_effect = [item, None]
    db.get.return_value = SimpleNamespace(email="user@example.invalid", status="active", is_deleted=False)
    now = datetime(2026, 9, 28, 18)
    monkeypatch.setattr(email_service, "beijing_now", lambda: now)
    monkeypatch.setattr(email_service, "send_email", MagicMock(side_effect=smtplib.SMTPAuthenticationError(535, b"private error")))
    result = email_service.dispatch_email_pending(db, limit=1)
    assert result == {"attempted": 1, "delivered": 0, "failed": 1}
    assert item.email_status == expected
    assert item.email_attempts == attempts+1
    assert "private error" not in item.email_last_error
    assert item.delivered_channels == ["in_app"]
    assert item.email_next_attempt_at == (now+timedelta(minutes=5) if attempts == 0 else None)


def test_success_updates_channel_once(monkeypatch, mail_settings):
    item = notification()
    db = MagicMock()
    db.scalar.return_value = item
    db.get.return_value = SimpleNamespace(email="user@example.invalid", status="active", is_deleted=False)
    monkeypatch.setattr(email_service, "send_email", lambda *args: True)
    assert email_service.dispatch_email_pending(db, limit=1)["delivered"] == 1
    assert item.email_status == "sent"
    assert item.delivered_channels == ["in_app", "email"]
