"""Scalar constants for the secure-share skill."""

ALL_DEFAULT_VIEWER_EMAILS: list[str] = ["melclombardi@gmail.com"]

ALL_OAUTH_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/cloud-platform",
]

ALL_HTML_EXTENSIONS: frozenset[str] = frozenset({".html", ".htm"})

OAUTH_CLIENT_ID: str = (
    "764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com"
)
OAUTH_CLIENT_SECRET: str = "d-FL95Q19q7MQmFpd7hHD0Ty"
OAUTH_AUTH_URI: str = "https://accounts.google.com/o/oauth2/auth"
OAUTH_TOKEN_URI: str = "https://oauth2.googleapis.com/token"

CALLBACK_HOST: str = "localhost"
CALLBACK_PORT: int = 8765
CALLBACK_REDIRECT_URI: str = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}/"
OAUTH_INSTALLED_REDIRECT_URI: str = "http://localhost"

OAUTH_INSTALLED_KEY: str = "installed"
OAUTH_REDIRECT_URIS_KEY: str = "redirect_uris"
OAUTH_FIELD_CLIENT_ID: str = "client_id"
OAUTH_FIELD_CLIENT_SECRET: str = "client_secret"
OAUTH_FIELD_AUTH_URI: str = "auth_uri"
OAUTH_FIELD_TOKEN_URI: str = "token_uri"
OAUTH_PROMPT_CONSENT: str = "consent"
OAUTH_ACCESS_TYPE_OFFLINE: str = "offline"

WSGI_QUERY_STRING_KEY: str = "QUERY_STRING"
WSGI_AUTH_CODE_KEY: str = "code"
WSGI_AUTH_ERROR_KEY: str = "error"
WSGI_OK_STATUS: str = "200 OK"
ALL_WSGI_CONTENT_TYPE_HEADERS: list[tuple[str, str]] = [("Content-Type", "text/html")]

QUOTA_PROJECT: str = "ynab-amazon-sync"

DRIVE_API_SERVICE: str = "drive"
DRIVE_API_VERSION: str = "v3"
DRIVE_VIEWER_ROLE: str = "reader"
DRIVE_PERMISSION_TYPE_USER: str = "user"
DRIVE_FILE_FIELDS: str = "id,name,webViewLink"
DRIVE_PERMISSION_FIELDS: str = "id"
DRIVE_FILE_NAME_KEY: str = "name"
DRIVE_FILE_ID_KEY: str = "id"
DRIVE_FILE_VIEW_LINK_KEY: str = "webViewLink"
DRIVE_PERMISSION_ROLE_KEY: str = "role"
DRIVE_PERMISSION_TYPE_KEY: str = "type"
DRIVE_PERMISSION_EMAIL_KEY: str = "emailAddress"

CHROME_FLAG_HEADLESS: str = "--headless"
CHROME_FLAG_DISABLE_GPU: str = "--disable-gpu"
CHROME_FLAG_NO_PDF_HEADER: str = "--no-pdf-header-footer"
CHROME_FLAG_PRINT_TO_PDF_PREFIX: str = "--print-to-pdf="
CHROME_FLAG_NEW_WINDOW: str = "--new-window"

LOGGER_NAME: str = "secure_share"
LOG_FORMAT: str = "%(levelname)s %(message)s"
OAUTHLIB_TRANSPORT_ENV_NAME: str = "OAUTHLIB_INSECURE_TRANSPORT"
OAUTHLIB_TRANSPORT_ENV_VALUE: str = "1"

OCTET_STREAM_MIME_TYPE: str = "application/octet-stream"
PDF_FILE_EXTENSION: str = ".pdf"

TOKEN_PATH_HOME_RELATIVE: str = ".claude/state/secure-share/drive_token.json"
TOKEN_PATH_PLUGIN_DATA_RELATIVE: str = "secure-share/drive_token.json"
TOKEN_FILE_PERMISSIONS: int = 0o600
CLAUDE_PLUGIN_DATA_ENV_NAME: str = "CLAUDE_PLUGIN_DATA"

CHROME_STDERR_DECODE_ERRORS: str = "replace"

ALL_CHROME_PATH_CANDIDATES: list[str] = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
]

CALLBACK_SUCCESS_BODY: bytes = b"<h1>Signed in. You can close this tab.</h1>"
CALLBACK_FAILURE_BODY: bytes = b"<h1>No authorization code in callback.</h1>"

DEFAULT_FILE_TITLE_PREFIX: str = "Shared via secure-share — "
