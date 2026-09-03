from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
from dataclasses import dataclass
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener

from . import __version__
from .models import DiscardAction, InboxItem, MailDetail
from .parser import parse_html, parse_inbox, parse_mail_detail


DEFAULT_BASE_URL = "https://mailmate.jp"
DEFAULT_COOKIE_JAR = Path.home() / ".local" / "state" / "mailmate-cli" / "cookies.txt"
DEFAULT_ENV_FILE = Path.home() / ".config" / "mailmate-cli" / "env"


class MailMateError(RuntimeError):
    pass


class AuthRequiredError(MailMateError):
    pass


@dataclass(frozen=True)
class Credentials:
    email: str
    password: str


class MailMateClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, cookie_jar: Path = DEFAULT_COOKIE_JAR) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookie_jar_path = Path(cookie_jar).expanduser()
        self.cookie_jar_path.parent.mkdir(parents=True, exist_ok=True)
        self.cookie_jar = MozillaCookieJar(str(self.cookie_jar_path))
        if self.cookie_jar_path.exists():
            try:
                self.cookie_jar.load(ignore_discard=True, ignore_expires=True)
            except Exception:
                self.cookie_jar = MozillaCookieJar(str(self.cookie_jar_path))
        self.opener = build_opener(HTTPCookieProcessor(self.cookie_jar), HTTPSHandler(context=_ssl_context()))

    def save_cookies(self) -> None:
        self.cookie_jar.save(ignore_discard=True, ignore_expires=True)
        try:
            self.cookie_jar_path.chmod(0o600)
        except OSError:
            pass

    def request(
        self,
        path_or_url: str,
        *,
        method: str = "GET",
        fields: dict[str, str] | None = None,
        referer: str | None = None,
        accept: str = "text/html,application/xhtml+xml",
    ) -> tuple[str, str]:
        url = path_or_url if path_or_url.startswith("http") else urljoin(self.base_url + "/", path_or_url.lstrip("/"))
        body = None
        headers = {
            "User-Agent": f"mailmate-cli/{__version__} (+local automation)",
            "Accept": accept,
            "Accept-Language": "ja,en;q=0.8",
        }
        if referer:
            headers["Referer"] = referer
        if method.upper() not in {"GET", "HEAD"}:
            body = urlencode(fields or {}).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            headers["Origin"] = self.base_url
        request = Request(url, data=body, method=method.upper(), headers=headers)
        try:
            response = self.opener.open(request, timeout=30)
        except HTTPError as exc:
            raise MailMateError(f"MailMate request failed: HTTP {exc.code} {url}") from exc
        except URLError as exc:
            raise MailMateError(f"MailMate request failed: {exc.reason}") from exc
        content = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        final_url = response.geturl()
        return content.decode(charset, errors="replace"), final_url

    def ensure_authenticated(
        self, credentials_or_getter: Credentials | None | Callable[[], Credentials | None] = None
    ) -> None:
        html, final_url = self.request("/app/mails")
        if not _is_sign_in_page(html, final_url):
            self.save_cookies()
            return
        credentials = credentials_or_getter() if callable(credentials_or_getter) else credentials_or_getter
        if credentials is None:
            raise AuthRequiredError("MailMate login required. Provide MAILMATE_EMAIL/MAILMATE_PASSWORD or --op-item.")
        self.login(credentials)

    def login(self, credentials: Credentials) -> None:
        html, sign_in_url = self.request("/users/sign_in")
        parser = parse_html(html)
        form = next((f for f in parser.forms if str(f.get("action", "")).endswith("/users/sign_in")), None)
        if form is None:
            raise AuthRequiredError("Could not find MailMate sign-in form.")
        fields = dict(form.get("fields", {}))
        fields["user[email]"] = credentials.email
        fields["user[password]"] = credentials.password
        fields["user[remember_me]"] = "1"
        fields["commit"] = "Sign In"
        action = str(form.get("action") or "/users/sign_in")
        response_html, final_url = self.request(action, method="POST", fields=fields, referer=sign_in_url)
        if _is_sign_in_page(response_html, final_url):
            raise AuthRequiredError("MailMate login failed or requires additional verification.")
        self.save_cookies()

    def inbox(self, inbox_id: str | None = None, limit: int = 50) -> list[InboxItem]:
        path = f"/app/mails?inbox_id={inbox_id}" if inbox_id else "/app/mails"
        html, final_url = self.request(path)
        if _is_sign_in_page(html, final_url):
            raise AuthRequiredError("MailMate login required.")
        return parse_inbox(html, final_url)[:limit]

    def detail(self, mail_id: str, *, scan_requested: bool = False) -> MailDetail:
        html, final_url = self.request(f"/app/mails/{mail_id}/view_mail")
        if _is_sign_in_page(html, final_url):
            raise AuthRequiredError("MailMate login required.")
        return parse_mail_detail(html, final_url, scan_requested=scan_requested)

    def download_pdf_bytes(self, mail_id_or_url: str, referer: str | None = None) -> bytes:
        if str(mail_id_or_url).isdigit():
            target_path = f"/app/mails/{mail_id_or_url}/generate_pdf"
            ref = referer or f"{self.base_url}/app/mails/{mail_id_or_url}/view_mail"
        else:
            target_path = str(mail_id_or_url)
            ref = referer
        url = target_path if target_path.startswith("http") else urljoin(self.base_url + "/", target_path.lstrip("/"))
        headers = {
            "User-Agent": f"mailmate-cli/{__version__} (+local automation)",
            "Accept": "application/pdf,*/*",
        }
        if ref:
            headers["Referer"] = ref
        request = Request(url, headers=headers)
        try:
            response = self.opener.open(request, timeout=60)
            return response.read()
        except HTTPError as exc:
            raise MailMateError(f"PDF download failed: HTTP {exc.code} {url}") from exc
        except URLError as exc:
            raise MailMateError(f"PDF download failed: {exc.reason}") from exc

    def submit_discard(self, action: DiscardAction, referer: str) -> tuple[str, str]:
        fields = dict(action.fields)
        method = action.method.upper()
        if method not in {"GET", "POST"}:
            fields["_method"] = method.lower()
            method = "POST"
        html, final_url = self.request(action.url, method=method, fields=fields, referer=referer)
        self.save_cookies()
        return html, final_url


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    if not pdf_bytes:
        return ""
    try:
        import fitz  # type: ignore

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages: list[str] = []
        for idx in range(len(doc)):
            text = doc[idx].get_text().strip()
            if text:
                pages.append(f"--- Page {idx + 1} ---\n{text}")
        if pages:
            return "\n\n".join(pages)
    except Exception:
        pass

    try:
        proc = subprocess.run(
            ["pdftotext", "-", "-"],
            input=pdf_bytes,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            out = proc.stdout.decode("utf-8", errors="replace").strip()
            if out:
                return out
    except Exception:
        pass

    return ""


def resolve_credentials(
    *,
    email: str | None = None,
    password_env: str = "MAILMATE_PASSWORD",
    op_item: str | None = None,
    env_file: Path | str | None = None,
) -> Credentials | None:
    env_values = load_env_file(Path(env_file)) if env_file else {}
    email = email or os.environ.get("MAILMATE_EMAIL") or env_values.get("MAILMATE_EMAIL")
    password = os.environ.get(password_env) or env_values.get(password_env)
    if email and password:
        return Credentials(email=email, password=password)
    op_item = op_item or os.environ.get("MAILMATE_OP_ITEM") or env_values.get("MAILMATE_OP_ITEM")
    if op_item:
        return _credentials_from_1password(op_item, email=email)
    return None


def load_env_file(path: Path) -> dict[str, str]:
    path = path.expanduser()
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _credentials_from_1password(item: str, *, email: str | None = None) -> Credentials:
    command = ["op", "item", "get", item, "--format", "json"]
    try:
        proc = subprocess.run(command, check=True, capture_output=True, text=True, timeout=45)
    except FileNotFoundError as exc:
        raise AuthRequiredError("1Password CLI is not installed.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AuthRequiredError("1Password authorization timed out.") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() or "unknown 1Password error"
        raise AuthRequiredError(f"1Password lookup failed: {stderr}") from exc
    data = json.loads(proc.stdout)
    fields = data.get("fields", [])
    by_label = {str(f.get("label", "")).lower(): f.get("value") for f in fields}
    by_id = {str(f.get("id", "")).lower(): f.get("value") for f in fields}
    resolved_email = email or by_label.get("username") or by_label.get("email") or by_id.get("username")
    resolved_password = by_label.get("password") or by_id.get("password")
    if not resolved_email or not resolved_password:
        raise AuthRequiredError("1Password item did not contain username/email and password fields.")
    return Credentials(email=str(resolved_email), password=str(resolved_password))


def _is_sign_in_page(html: str, url: str) -> bool:
    return "/users/sign_in" in url or 'id="new_user"' in html or 'name="user[email]"' in html


def print_error(message: str) -> None:
    print(message, file=sys.stderr)


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()
