"""Send a finished transcript to the client's email."""

import json
import logging
import os
import re
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def smtp_settings_path() -> str:
    db_path = os.getenv("DATABASE_PATH", "transcription.db")
    directory = os.path.dirname(db_path) or "."
    return os.path.join(directory, "smtp.json")


def default_smtp_settings() -> dict:
    security = os.getenv("SMTP_SECURITY", "STARTTLS").strip().upper()
    try:
        port = int(os.getenv("SMTP_PORT", "587") or 587)
    except ValueError:
        port = 587
    return {
        "host": os.getenv("SMTP_HOST", "").strip(),
        "port": port,
        "username": os.getenv("SMTP_USERNAME", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from_addr": os.getenv("SMTP_FROM", "").strip(),
        "use_tls": security != "SSL",
        "use_ssl": security == "SSL",
    }


def load_smtp_settings() -> dict:
    settings = default_smtp_settings()
    path = smtp_settings_path()
    if not os.path.exists(path):
        return settings
    try:
        with open(path, encoding="utf-8") as handle:
            saved = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read SMTP settings: %s", exc)
        return settings
    for key in settings:
        if key in saved:
            settings[key] = saved[key]
    return settings


def save_smtp_settings(settings: dict) -> None:
    path = smtp_settings_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    stored = {
        "host": str(settings.get("host", "")).strip(),
        "port": int(settings.get("port") or 587),
        "username": str(settings.get("username", "")).strip(),
        "password": str(settings.get("password", "")),
        "from_addr": str(settings.get("from_addr", "")).strip(),
        "use_tls": bool(settings.get("use_tls")),
        "use_ssl": bool(settings.get("use_ssl")),
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(stored, handle, indent=2)


def smtp_is_configured(settings: dict | None = None) -> bool:
    settings = settings if settings is not None else load_smtp_settings()
    sender = (settings.get("from_addr") or settings.get("username") or "").strip()
    return bool(settings.get("host") and sender)


def _attachment_name(filename: str, suffix: str = "") -> str:
    base = os.path.splitext(os.path.basename(filename or "transcript"))[0]
    safe = "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in base).strip(" .")
    safe = safe or "transcript"
    if suffix:
        return f"{safe}.{suffix}.txt"
    return f"{safe}.txt"


def _header(value: str) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def _connect(settings: dict):
    host = settings["host"]
    port = int(settings["port"])
    if settings.get("use_ssl"):
        server = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
        server.ehlo()
        if settings.get("use_tls"):
            server.starttls()
            server.ehlo()
    username = (settings.get("username") or "").strip()
    if username:
        server.login(username, settings.get("password") or "")
    return server


def _send(settings: dict, message: EmailMessage) -> None:
    server = _connect(settings)
    try:
        server.send_message(message)
    finally:
        try:
            server.quit()
        except Exception:
            pass


def send_test_email(settings: dict, to_addr: str) -> tuple[bool, str]:
    sender = (settings.get("from_addr") or settings.get("username") or "").strip()
    recipient = (to_addr or sender).strip()
    if not smtp_is_configured(settings):
        return False, "Fill in the SMTP host and the From address, then save."
    if not _EMAIL_RE.match(recipient):
        return False, f"Invalid email address: {recipient}"

    message = EmailMessage()
    message["Subject"] = "Video Transcription: test"
    message["From"] = _header(sender)
    message["To"] = _header(recipient)
    message.set_content(
        "Проверка отправки из Video Transcription.\n"
        "Это тестовое письмо, расшифровки здесь нет.\n",
        charset="utf-8",
    )
    try:
        _send(settings, message)
    except Exception as exc:
        logger.exception("Test email failed")
        return False, f"Could not send test email: {exc}"
    return True, f"Test email sent to {recipient}"


def email_transcript_to_client(
    client_id: int,
    filename: str,
    transcript: str,
    translated_text: str | None = None,
    target_language: str | None = None,
) -> tuple[bool, str]:
    """Send the transcript to the email stored on the client."""
    from database import TranscriptionDB

    settings = load_smtp_settings()
    if not smtp_is_configured(settings):
        return False, "Transcript was not emailed. Set the SMTP server under Email in the sidebar."

    client = TranscriptionDB().get_client_by_id(client_id)
    if not client:
        return False, "Transcript was not emailed. Client was not found."

    _client_id, client_name, email = client
    email = (email or "").strip()
    if not _EMAIL_RE.match(email):
        return False, f"Transcript was not emailed. Client email is invalid: {email or 'empty'}"
    if not (transcript or "").strip():
        return False, "Transcript was not emailed. The transcript is empty."

    sender = (settings.get("from_addr") or settings.get("username") or "").strip()
    name = client_name or "клиент"
    body = (
        f"Здравствуйте, {name}.\n\n"
        f"Расшифровка файла «{filename}» во вложении.\n"
    )
    if translated_text and target_language and target_language != "None":
        body += f"Перевод ({target_language}) тоже во вложении.\n"
    body += "\n—\nVideo Transcription\n"

    message = EmailMessage()
    message["Subject"] = _header(f"Расшифровка: {filename}")
    message["From"] = _header(sender)
    message["To"] = _header(email)
    message.set_content(body, charset="utf-8")
    message.add_attachment(
        transcript.encode("utf-8"),
        maintype="text",
        subtype="plain",
        filename=_attachment_name(filename),
    )
    if translated_text and target_language and target_language != "None":
        message.add_attachment(
            translated_text.encode("utf-8"),
            maintype="text",
            subtype="plain",
            filename=_attachment_name(filename, suffix=target_language),
        )

    try:
        _send(settings, message)
    except Exception as exc:
        logger.exception("Transcript email failed")
        return False, f"Transcript was not emailed: {exc}"
    return True, f"Transcript sent to {email}"
