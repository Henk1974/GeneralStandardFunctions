import smtplib
from email.utils import parseaddr
from unittest.mock import MagicMock, patch

import pytest

from general_standard_functions.mail.smtp import MailError, SmtpMailer
from general_standard_functions.storage.images import ImageUploadService, InvalidImageError
from general_standard_functions.storage.supabase import SupabaseStorageError, SupabaseStorageProvider

SMTP = "general_standard_functions.mail.smtp.smtplib.SMTP"


def _send(**kwargs):
    smtp = MagicMock()
    with patch(SMTP) as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = smtp
        SmtpMailer("smtp.example.com", 587, "app@example.com", "pw", default_from_name="MijnApp").send(**kwargs)
    return smtp_cls, smtp, smtp.send_message.call_args.args[0]


def test_send_uses_starttls_login_and_headers():
    smtp_cls, smtp, msg = _send(to="a@example.com", subject="Onderwerp", body="Tekst", reply_to="b@example.nl")
    smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=15.0)
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("app@example.com", "pw")
    assert msg["To"] == "a@example.com" and msg["Reply-To"] == "b@example.nl"
    assert parseaddr(msg["From"]) == ("MijnApp", "app@example.com")


def test_from_name_overrides_default():
    _, _, msg = _send(to="a@example.com", subject="x", body="y", from_name="Henk via MijnApp")
    assert parseaddr(msg["From"]) == ("Henk via MijnApp", "app@example.com")


def test_header_injection_is_neutralised():
    _, _, msg = _send(to="a@example.com", subject="Hoi\r\nBcc: spam@example.com", body="y")
    assert msg["Bcc"] is None and "\n" not in msg["Subject"]


def test_smtp_failure_becomes_mail_error():
    with patch(SMTP) as smtp_cls:
        smtp_cls.return_value.__enter__.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, b"nee")
        with pytest.raises(MailError):
            SmtpMailer("h", 587, "u", "p").send("a@example.com", "x", "y")


# --- afbeeldingen --------------------------------------------------------


def test_disallowed_extension_is_refused():
    with pytest.raises(InvalidImageError):
        ImageUploadService(upload_folder="/tmp").save("malware.exe", b"x", "application/octet-stream")


def test_local_folder_gets_uuid_name(tmp_path):
    url = ImageUploadService(upload_folder=str(tmp_path), public_url_prefix="/media/").save("Foto.JPG", b"data", "image/jpeg")
    assert url.startswith("/media/") and url.endswith(".jpg") and "Foto" not in url
    assert (tmp_path / url.rsplit("/", 1)[-1]).read_bytes() == b"data"


def test_storage_provider_has_priority(tmp_path):
    provider = MagicMock()
    provider.upload.return_value = "https://cdn.example/abc.png"
    service = ImageUploadService(upload_folder=str(tmp_path), storage_provider=provider)
    assert service.save("x.png", b"d", "image/png") == "https://cdn.example/abc.png"
    assert list(tmp_path.iterdir()) == []


def test_no_storage_configured_raises():
    with pytest.raises(RuntimeError):
        ImageUploadService().save("x.png", b"d", "image/png")


# --- Supabase Storage ----------------------------------------------------


def test_supabase_upload_returns_public_url():
    with patch("general_standard_functions.storage.supabase.requests.post") as post:
        post.return_value.status_code = 200
        url = SupabaseStorageProvider("https://p.supabase.co/", "key", "media").upload("a.jpg", b"d", "image/jpeg")
    assert url == "https://p.supabase.co/storage/v1/object/public/media/a.jpg"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer key"


def test_supabase_error_status_raises():
    with patch("general_standard_functions.storage.supabase.requests.post") as post:
        post.return_value.status_code = 403
        post.return_value.text = "forbidden"
        with pytest.raises(SupabaseStorageError, match="403"):
            SupabaseStorageProvider("https://p.supabase.co", "key", "media").upload("a.jpg", b"d", "image/jpeg")
