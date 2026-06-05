"""Publish a file to Google Drive with restricted per-email access.

The script accepts a local file path plus any number of recipient emails
beyond the always-included default. HTML inputs are rendered to PDF via
Chrome headless so they show inline in Drive's web viewer. The first run
triggers a browser OAuth flow; later runs reuse the saved token.

Usage:
    python publish.py --input path/to/file.html
    python publish.py --input report.pdf --email alice@example.com
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import parse_qs
from wsgiref.simple_server import WSGIServer, make_server

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaFileUpload

_script_parent_dir = str(Path(__file__).resolve().parent)
if _script_parent_dir not in sys.path:
    sys.path.insert(0, _script_parent_dir)

from config.secure_share_constants import (
    ALL_CHROME_PATH_CANDIDATES,
    ALL_DEFAULT_VIEWER_EMAILS,
    ALL_HTML_EXTENSIONS,
    ALL_OAUTH_SCOPES,
    ALL_WSGI_CONTENT_TYPE_HEADERS,
    CALLBACK_FAILURE_BODY,
    CALLBACK_HOST,
    CALLBACK_PORT,
    CALLBACK_REDIRECT_URI,
    CALLBACK_SUCCESS_BODY,
    CHROME_FLAG_DISABLE_GPU,
    CHROME_FLAG_HEADLESS,
    CHROME_FLAG_NEW_WINDOW,
    CHROME_FLAG_NO_PDF_HEADER,
    CHROME_FLAG_PRINT_TO_PDF_PREFIX,
    DEFAULT_FILE_TITLE_PREFIX,
    DRIVE_API_SERVICE,
    DRIVE_API_VERSION,
    DRIVE_FILE_FIELDS,
    DRIVE_FILE_ID_KEY,
    DRIVE_FILE_NAME_KEY,
    DRIVE_FILE_VIEW_LINK_KEY,
    DRIVE_PERMISSION_EMAIL_KEY,
    DRIVE_PERMISSION_FIELDS,
    DRIVE_PERMISSION_ROLE_KEY,
    DRIVE_PERMISSION_TYPE_KEY,
    DRIVE_PERMISSION_TYPE_USER,
    DRIVE_VIEWER_ROLE,
    LOG_FORMAT,
    LOGGER_NAME,
    OAUTH_ACCESS_TYPE_OFFLINE,
    OAUTH_FIELD_AUTH_URI,
    OAUTH_FIELD_CLIENT_ID,
    OAUTH_FIELD_CLIENT_SECRET,
    OAUTH_FIELD_TOKEN_URI,
    OAUTH_INSTALLED_KEY,
    OAUTH_INSTALLED_REDIRECT_URI,
    OAUTH_AUTH_URI,
    OAUTH_CLIENT_ID,
    OAUTH_CLIENT_SECRET,
    OAUTH_PROMPT_CONSENT,
    OAUTH_REDIRECT_URIS_KEY,
    OAUTH_TOKEN_URI,
    OAUTHLIB_TRANSPORT_ENV_NAME,
    OAUTHLIB_TRANSPORT_ENV_VALUE,
    CLAUDE_PLUGIN_DATA_ENV_NAME,
    PDF_FILE_EXTENSION,
    PDF_MIME_TYPE,
    QUOTA_PROJECT,
    TOKEN_PATH_HOME_RELATIVE,
    TOKEN_PATH_PLUGIN_DATA_RELATIVE,
    WSGI_AUTH_CODE_KEY,
    WSGI_OK_STATUS,
    WSGI_QUERY_STRING_KEY,
)

os.environ[OAUTHLIB_TRANSPORT_ENV_NAME] = OAUTHLIB_TRANSPORT_ENV_VALUE

_logger = logging.getLogger(LOGGER_NAME)

WsgiStatusEmitter = Callable[[str, list[tuple[str, str]]], object]


def _resolve_token_path() -> Path:
    plugin_storage_root = os.environ.get(CLAUDE_PLUGIN_DATA_ENV_NAME)
    if plugin_storage_root:
        return Path(plugin_storage_root) / TOKEN_PATH_PLUGIN_DATA_RELATIVE
    return Path.home() / TOKEN_PATH_HOME_RELATIVE


def _is_html_input(source_path: Path) -> bool:
    return source_path.suffix.lower() in ALL_HTML_EXTENSIONS


def _find_chrome_executable() -> Path | None:
    for each_raw_candidate in ALL_CHROME_PATH_CANDIDATES:
        candidate_path = Path(os.path.expandvars(each_raw_candidate))
        if candidate_path.exists():
            return candidate_path
    return None


def _convert_html_to_pdf(source_path: Path) -> Path:
    """Render the HTML file to a sibling PDF via Chrome headless.

    Args:
        source_path: Absolute path to the input HTML file.

    Returns:
        Absolute path to the generated PDF (sibling of the input).

    Raises:
        RuntimeError: When Chrome cannot be located on the host.
    """
    chrome_executable = _find_chrome_executable()
    if chrome_executable is None:
        raise RuntimeError(
            "Chrome executable not found; install Chrome or pass a PDF input."
        )
    pdf_destination = source_path.with_suffix(PDF_FILE_EXTENSION)
    subprocess.run(
        [
            str(chrome_executable),
            CHROME_FLAG_HEADLESS,
            CHROME_FLAG_DISABLE_GPU,
            CHROME_FLAG_NO_PDF_HEADER,
            f"{CHROME_FLAG_PRINT_TO_PDF_PREFIX}{pdf_destination}",
            source_path.as_uri(),
        ],
        check=True,
        capture_output=True,
    )
    _logger.info("Rendered HTML to PDF: %s", pdf_destination)
    return pdf_destination


def _open_in_chrome(target_url: str) -> None:
    chrome_executable = _find_chrome_executable()
    if chrome_executable is not None:
        subprocess.Popen([str(chrome_executable), CHROME_FLAG_NEW_WINDOW, target_url])
        return
    webbrowser.open(target_url, new=1, autoraise=True)


def _load_saved_token() -> Credentials | None:
    token_path = _resolve_token_path()
    if not token_path.exists():
        return None
    saved = Credentials.from_authorized_user_file(str(token_path))
    if not saved.scopes:
        return None
    if not set(ALL_OAUTH_SCOPES).issubset(set(saved.scopes)):
        return None
    return saved


def _save_token(credentials: Credentials) -> None:
    token_path = _resolve_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json())


def _build_oauth_flow() -> InstalledAppFlow:
    client_config = {
        OAUTH_INSTALLED_KEY: {
            OAUTH_FIELD_CLIENT_ID: OAUTH_CLIENT_ID,
            OAUTH_FIELD_CLIENT_SECRET: OAUTH_CLIENT_SECRET,
            OAUTH_FIELD_AUTH_URI: OAUTH_AUTH_URI,
            OAUTH_FIELD_TOKEN_URI: OAUTH_TOKEN_URI,
            OAUTH_REDIRECT_URIS_KEY: [OAUTH_INSTALLED_REDIRECT_URI],
        }
    }
    return InstalledAppFlow.from_client_config(client_config, scopes=ALL_OAUTH_SCOPES)


class _CallbackCapture:
    def __init__(self) -> None:
        self.captured_url: str | None = None

    def __call__(
        self,
        all_environ: dict[str, str],
        emit_status: WsgiStatusEmitter,
    ) -> list[bytes]:
        """Capture the OAuth code from the localhost callback request.

        Args:
            all_environ: WSGI environ mapping for the inbound request.
            emit_status: WSGI start_response callable for status + headers.

        Returns:
            HTML body bytes to surface in the browser tab.
        """
        query_string = all_environ.get(WSGI_QUERY_STRING_KEY, "")
        if WSGI_AUTH_CODE_KEY in parse_qs(query_string):
            self.captured_url = f"{CALLBACK_REDIRECT_URI}?{query_string}"
            body = CALLBACK_SUCCESS_BODY
        else:
            body = CALLBACK_FAILURE_BODY
        emit_status(WSGI_OK_STATUS, ALL_WSGI_CONTENT_TYPE_HEADERS)
        return [body]


def _run_oauth_flow() -> Credentials:
    flow = _build_oauth_flow()
    flow.redirect_uri = CALLBACK_REDIRECT_URI
    auth_url, _state = flow.authorization_url(
        prompt=OAUTH_PROMPT_CONSENT,
        access_type=OAUTH_ACCESS_TYPE_OFFLINE,
    )
    _logger.info("Opening Chrome for Google sign-in: %s", auth_url)
    _open_in_chrome(auth_url)
    capture = _CallbackCapture()
    callback_server: WSGIServer = make_server(CALLBACK_HOST, CALLBACK_PORT, capture)
    while capture.captured_url is None:
        callback_server.handle_request()
    flow.fetch_token(authorization_response=capture.captured_url)
    credentials = flow.credentials
    _save_token(credentials)
    _logger.info("OAuth token saved at %s", _resolve_token_path())
    return credentials


def _get_credentials() -> Credentials:
    saved = _load_saved_token()
    if saved is not None:
        _logger.info("Reusing saved token at %s", _resolve_token_path())
        return saved
    return _run_oauth_flow()


def _build_drive_service(credentials: Credentials) -> Resource:
    credentials_with_quota = credentials.with_quota_project(QUOTA_PROJECT)
    return build(
        DRIVE_API_SERVICE, DRIVE_API_VERSION, credentials=credentials_with_quota
    )


def _upload_file(
    service: Resource, file_path: Path, drive_title: str
) -> dict[str, str]:
    media = MediaFileUpload(str(file_path), mimetype=PDF_MIME_TYPE, resumable=True)
    return (
        service.files()
        .create(
            body={DRIVE_FILE_NAME_KEY: drive_title},
            media_body=media,
            fields=DRIVE_FILE_FIELDS,
        )
        .execute()
    )


def _share_with_recipient(
    service: Resource, drive_file_id: str, recipient_email: str
) -> None:
    service.permissions().create(
        fileId=drive_file_id,
        body={
            DRIVE_PERMISSION_ROLE_KEY: DRIVE_VIEWER_ROLE,
            DRIVE_PERMISSION_TYPE_KEY: DRIVE_PERMISSION_TYPE_USER,
            DRIVE_PERMISSION_EMAIL_KEY: recipient_email,
        },
        sendNotificationEmail=False,
        fields=DRIVE_PERMISSION_FIELDS,
    ).execute()
    _logger.info("Shared with %s as %s", recipient_email, DRIVE_VIEWER_ROLE)


def _merge_recipients(all_extra_recipients: Iterable[str]) -> list[str]:
    all_recipients = list(ALL_DEFAULT_VIEWER_EMAILS)
    for each_recipient in all_extra_recipients:
        if each_recipient and each_recipient not in all_recipients:
            all_recipients.append(each_recipient)
    return all_recipients


def _parse_arguments(all_arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish a file to Drive with per-email restricted access.",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Local file to publish.",
    )
    parser.add_argument(
        "--email",
        action="append",
        default=[],
        help="Extra viewer email (repeat for multiple).",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Custom title shown in Drive (falls back to file name).",
    )
    return parser.parse_args(all_arguments)


def publish(
    file_path: Path,
    all_extra_recipients: Iterable[str] = (),
    drive_title: str | None = None,
) -> str:
    """Upload the file to Drive and share it with the recipient list.

    Args:
        file_path: Local path to the file to publish. HTML is converted to PDF.
        all_extra_recipients: Emails to add on top of the default viewer list.
        drive_title: Optional override for the Drive file title. Defaults to the
            source file's name.

    Returns:
        The Drive `webViewLink` URL ready for direct sharing.

    Raises:
        FileNotFoundError: If the input file does not exist.
        RuntimeError: If the input is HTML and Chrome cannot be located.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    upload_path = (
        _convert_html_to_pdf(file_path) if _is_html_input(file_path) else file_path
    )
    resolved_title = drive_title or (DEFAULT_FILE_TITLE_PREFIX + file_path.name)
    credentials = _get_credentials()
    service = _build_drive_service(credentials)
    uploaded = _upload_file(service, upload_path, resolved_title)
    drive_file_id = uploaded[DRIVE_FILE_ID_KEY]
    drive_view_link = uploaded[DRIVE_FILE_VIEW_LINK_KEY]
    for each_recipient_email in _merge_recipients(all_extra_recipients):
        _share_with_recipient(service, drive_file_id, each_recipient_email)
    _logger.info("Drive view link: %s", drive_view_link)
    return drive_view_link


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=sys.stderr)
    _parsed_cli = _parse_arguments(sys.argv[1:])
    _drive_view_link = publish(
        file_path=_parsed_cli.input,
        all_extra_recipients=_parsed_cli.email,
        drive_title=_parsed_cli.title,
    )
    sys.stdout.write(_drive_view_link + "\n")
