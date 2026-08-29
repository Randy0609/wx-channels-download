#!/usr/bin/env python3
"""Resolve and download WeChat Channels links through a local Yuanbao browser session."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import BrowserContext, Page, Request, sync_playwright
except ImportError as exc:
    raise SystemExit("PLAYWRIGHT_MISSING: use the platform runner and its explicit setup script") from exc


YUANBAO_ORIGIN = "https://yuanbao.tencent.com"
PARSE_URL = f"{YUANBAO_ORIGIN}/api/weixin/get_parse_result"
FEED_URL = "https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info"
LOGIN_COOKIE_GROUPS = (("hy_user", "hy_token"), ("yuanqi_user", "yuanqi_token"))
SHARE_RE = re.compile(r"^https://weixin\.qq\.com/sph/[A-Za-z0-9]+(?:[/?#].*)?$")
BROWSER_NAMES = ("edge", "chrome")
SKILL_VERSION = "1.1.0-randy.1"
DEFAULT_MAX_BYTES = 2 * 1024 * 1024 * 1024
CAPTURE_HEADER_NAMES = frozenset({
    "authorization",
    "accept-language",
    "t-userid",
    "x-agentid",
    "x-device-id",
    "x-hy92",
    "x-hy93",
    "x-id",
})


class SkillError(RuntimeError):
    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)


def default_root() -> Path:
    override = os.environ.get("WX_CHANNELS_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "wx-channels-download" if base else Path.home() / ".wx-channels-download"


def default_downloads() -> Path:
    path = Path.home() / "Downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def locate_browser(name: str) -> Path | None:
    if sys.platform == "darwin":
        relative = {
            "edge": "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "chrome": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        }[name]
        return Path(relative) if Path(relative).is_file() else None
    roots = (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA"))
    relative = {
        "edge": "Microsoft/Edge/Application/msedge.exe",
        "chrome": "Google/Chrome/Application/chrome.exe",
    }[name]
    return next((Path(root) / relative for root in roots if root and (Path(root) / relative).is_file()), None)


def available_browsers() -> dict[str, str]:
    return {name: str(path) for name in BROWSER_NAMES if (path := locate_browser(name)) is not None}


def load_settings(root: Path) -> dict[str, Any]:
    path = root / "settings.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_browser_choice(root: Path, browser: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "settings.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"browser": browser}, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def select_browser(root: Path, requested: str | None, required: bool = True) -> str | None:
    installed = available_browsers()
    selected = requested or load_settings(root).get("browser")
    if selected and selected not in BROWSER_NAMES:
        selected = None
    if selected and selected not in installed:
        raise SkillError("BROWSER_MISSING", f"Selected browser '{selected}' was not found", browser=selected, available_browsers=list(installed))
    if requested and selected:
        save_browser_choice(root, selected)
    if required and not selected:
        raise SkillError(
            "BROWSER_SELECTION_REQUIRED",
            "Choose Edge or Chrome before the first login or download",
            available_browsers=list(installed),
        )
    return selected


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def profile_for(root: Path, browser: str, override: str | None) -> Path:
    if override:
        candidate = Path(override).expanduser().resolve()
        profiles_root = (root / "profiles").expanduser().resolve()
        legacy = (root / "profile").expanduser().resolve()
        if candidate != legacy and not is_within(candidate, profiles_root):
            raise SkillError(
                "UNSAFE_PROFILE_DIR",
                "The browser profile must stay inside this Skill's dedicated profile directory",
                allowed_root=str(profiles_root),
            )
        return candidate
    legacy = root / "profile"
    current = root / "profiles" / browser
    if browser == "edge" and legacy.exists() and not current.exists():
        return legacy
    return current


def validate_share_url(value: str) -> str:
    value = value.strip()
    if not SHARE_RE.match(value):
        raise SkillError("INVALID_URL", "Only official https://weixin.qq.com/sph/ share links are supported")
    return value


def cookie_names(context: BrowserContext) -> set[str]:
    return {item.get("name", "") for item in context.cookies(YUANBAO_ORIGIN)}


def is_logged_in(context: BrowserContext) -> bool:
    names = cookie_names(context)
    return any(all(name in names for name in group) for group in LOGIN_COOKIE_GROUPS)


def request_header_score(headers: dict[str, str]) -> int:
    important = ("x-id", "x-agentid", "x-device-id", "x-hy92", "x-hy93", "t-userid", "authorization")
    return sum(3 for key in important if headers.get(key)) + sum(1 for key in headers if key.startswith("x-"))


def capture_safe_headers(raw_headers: dict[str, str]) -> dict[str, str]:
    """Keep only Yuanbao API authentication fields required for same-origin replay."""
    normalized = {str(key).lower(): str(value) for key, value in raw_headers.items()}
    return {
        key: value
        for key, value in normalized.items()
        if key in CAPTURE_HEADER_NAMES
    }


def attach_header_capture(page: Page, state: dict[str, Any]) -> None:
    def on_request(request: Request) -> None:
        try:
            parsed = urllib.parse.urlparse(request.url)
            if parsed.hostname != "yuanbao.tencent.com" or "/api/" not in parsed.path:
                return
            headers = capture_safe_headers(request.all_headers())
            score = request_header_score(headers)
            if score > state.get("score", -1):
                state.update(score=score, headers=headers, source_path=parsed.path)
        except Exception:
            return

    page.on("request", on_request)


def browser_context(playwright: Any, profile: Path, headless: bool, browser: str) -> BrowserContext:
    executable = locate_browser(browser)
    if executable is None:
        raise SkillError("BROWSER_MISSING", f"Selected browser '{browser}' was not found", browser=browser)
    profile.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile),
        executable_path=str(executable),
        headless=headless,
        viewport={"width": 1280, "height": 850},
        args=["--no-first-run", "--disable-default-apps", "--disable-features=Translate"],
    )


def wait_for_login(context: BrowserContext, page: Page, timeout: int) -> bool:
    if is_logged_in(context):
        return False
    if page.url == "about:blank" or "yuanbao.tencent.com" not in page.url:
        page.goto(YUANBAO_ORIGIN, wait_until="domcontentloaded", timeout=60_000)
    print("LOGIN_REQUIRED: complete login in the visible Yuanbao browser window", file=sys.stderr, flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_logged_in(context):
            page.wait_for_timeout(2500)
            return True
        page.wait_for_timeout(1000)
    raise SkillError("LOGIN_TIMEOUT", f"Yuanbao login was not detected within {timeout} seconds")


def prepare_page(context: BrowserContext, timeout: int, headless: bool) -> tuple[Page, dict[str, Any]]:
    page = context.pages[0] if context.pages else context.new_page()
    capture: dict[str, Any] = {"score": -1, "headers": {}}
    attach_header_capture(page, capture)
    page.goto(YUANBAO_ORIGIN, wait_until="domcontentloaded", timeout=60_000)
    newly_logged_in = wait_for_login(context, page, timeout)
    if newly_logged_in:
        capture.update(score=-1, headers={}, source_path=None)
        page.reload(wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(5000)
    else:
        page.wait_for_timeout(5000)
        if capture["score"] < 0:
            page.reload(wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(5000)
    if capture["score"] < 0:
        raise SkillError("NO_CAPTURED_HEADERS", "No authenticated Yuanbao API request headers were observed")
    if headless and not is_logged_in(context):
        raise SkillError("LOGIN_REQUIRED", "Run login without --headless first")
    return page, capture


def clear_dedicated_yuanbao_session(context: BrowserContext, page: Page) -> None:
    """Clear auth state only inside this Skill's dedicated persistent browser context."""
    if "yuanbao.tencent.com" not in page.url:
        page.goto(YUANBAO_ORIGIN, wait_until="domcontentloaded", timeout=60_000)
    try:
        page.evaluate("""() => { localStorage.clear(); sessionStorage.clear(); }""")
    except Exception:
        pass
    context.clear_cookies()


def refresh_capture_after_login(
    context: BrowserContext,
    page: Page,
    capture: dict[str, Any],
    timeout: int,
) -> None:
    page.goto(YUANBAO_ORIGIN, wait_until="domcontentloaded", timeout=60_000)
    wait_for_login(context, page, timeout)
    capture.update(score=-1, headers={}, source_path=None)
    page.reload(wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(5000)
    if capture["score"] < 0:
        raise SkillError("NO_CAPTURED_HEADERS", "No authenticated Yuanbao API request headers were observed after login")


def browser_fetch_parse(page: Page, share_url: str, captured: dict[str, str]) -> dict[str, Any]:
    headers = capture_safe_headers(captured)
    result = page.evaluate(
        """async ({url, payload, headers}) => {
          const response = await fetch(url, {
            method: 'POST', credentials: 'include',
            headers: {...headers, 'accept': 'application/json, text/plain, */*', 'content-type': 'application/json'},
            body: JSON.stringify(payload)
          });
          return {status: response.status, text: await response.text()};
        }""",
        {"url": PARSE_URL, "payload": {"type": "video_channel_url", "url": share_url, "scene": 1}, "headers": headers},
    )
    status = int(result.get("status", 0))
    try:
        payload = json.loads(result.get("text", ""))
    except json.JSONDecodeError as exc:
        raise SkillError("YUANBAO_BAD_RESPONSE", f"Yuanbao returned non-JSON data (HTTP {status})") from exc
    if status == 401:
        raise SkillError("YUANBAO_AUTH_FAILED", "Yuanbao rejected the saved session", http_status=status)
    if status < 200 or status >= 300 or payload.get("code") not in (0, None):
        raise SkillError("YUANBAO_PARSE_FAILED", str(payload.get("msg") or f"Yuanbao parse request failed with HTTP {status}"), http_status=status, remote_code=payload.get("code"))
    data = payload.get("data") or {}
    if not (data.get("playable_url") or data.get("playableUrl")):
        raise SkillError("YUANBAO_NO_PLAYABLE_URL", "Yuanbao response did not include a playable URL")
    return data


def get_feed(context: BrowserContext, parse_data: dict[str, Any]) -> dict[str, Any]:
    playable = urllib.parse.urlparse(parse_data.get("playable_url") or parse_data.get("playableUrl"))
    query = urllib.parse.parse_qs(playable.query)
    token = (query.get("token") or [""])[0]
    export_id = (query.get("eid") or [""])[0]
    if not token or not export_id:
        raise SkillError("TOKEN_MISSING", "The parsed URL did not include generalToken and exportId")
    referer = "https://channels.weixin.qq.com/finder-preview/pages/feed" + f"?token={urllib.parse.quote(token)}&eid={urllib.parse.quote(export_id)}"
    response = context.request.post(
        FEED_URL,
        headers={"Accept": "application/json, text/plain, */*", "Origin": "https://channels.weixin.qq.com", "Referer": referer},
        data={"baseReq": {"generalToken": token}, "exportId": export_id},
        timeout=30_000,
    )
    try:
        payload = response.json()
    except Exception as exc:
        raise SkillError("WEIXIN_BAD_RESPONSE", f"Weixin returned non-JSON data (HTTP {response.status})") from exc
    if not response.ok or payload.get("errCode", 0) != 0:
        raise SkillError("WEIXIN_PARSE_FAILED", str(payload.get("errMsg") or f"Weixin feed request failed with HTTP {response.status}"), http_status=response.status, remote_code=payload.get("errCode"))
    return payload.get("data") or {}


def validate_media_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
        raise SkillError("UNSAFE_MEDIA_URL", "The resolved media URL must be an authenticated HTTPS URL without embedded credentials")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        raise SkillError("UNSAFE_MEDIA_URL", "The resolved media URL points to a local hostname")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return value
    if not address.is_global:
        raise SkillError("UNSAFE_MEDIA_URL", "The resolved media URL points to a non-public IP address")
    return value


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        validate_media_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def media_url(feed: dict[str, Any], codec: str) -> str:
    info_key = "h265VideoInfo" if codec == "h265" else "h264VideoInfo"
    fallback_key = "h264VideoInfo" if codec == "h265" else "h265VideoInfo"
    url = (feed.get(info_key) or {}).get("videoUrl") or feed.get("videoUrl") or (feed.get(fallback_key) or {}).get("videoUrl")
    if not url:
        raise SkillError("MEDIA_URL_MISSING", "The feed response did not include a downloadable video URL")
    return validate_media_url(str(url))


def clean_filename(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", value).strip(" .")
    value = value.rstrip(" ._")
    if not value:
        value = f"wx_channels_{int(time.time())}"
    return value[:100].rstrip(" .") or f"wx_channels_{int(time.time())}"


def unique_path(directory: Path, stem: str) -> Path:
    candidate = directory / f"{stem}.mp4"
    index = 1
    while candidate.exists() or candidate.with_suffix(candidate.suffix + ".part").exists():
        candidate = directory / f"{stem} ({index}).mp4"
        index += 1
    return candidate


def is_preview_safe(path: Path) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+\.mp4", path.name))


def unique_preview_path(directory: Path, stem: str) -> Path:
    candidate = directory / f"{stem}.mp4"
    index = 2
    while candidate.exists() or candidate.with_suffix(candidate.suffix + ".part").exists():
        candidate = directory / f"{stem}-{index}.mp4"
        index += 1
    return candidate


def share_id(share_url: str) -> str:
    value = urllib.parse.urlparse(share_url).path.rstrip("/").rsplit("/", 1)[-1]
    return value if re.fullmatch(r"[A-Za-z0-9]+", value) else "video"


def ensure_preview_path(destination: Path, share_url: str) -> tuple[Path, str]:
    """Create a Markdown-safe alias without duplicating bytes when hard links are available."""
    if is_preview_safe(destination):
        return destination, "original"
    preview = unique_preview_path(destination.parent, f"wechat_video_{share_id(share_url)}")
    try:
        os.link(destination, preview)
        return preview, "hardlink"
    except OSError:
        try:
            shutil.copy2(destination, preview)
            return preview, "copy"
        except OSError:
            return destination, "unavailable"


def download_video(url: str, destination: Path, max_bytes: int) -> tuple[int, str, str]:
    if max_bytes <= 0:
        raise SkillError("INVALID_SIZE_LIMIT", "The media size limit must be greater than zero")
    validate_media_url(url)
    part = destination.with_suffix(destination.suffix + ".part")
    digest, first, size = hashlib.sha256(), b"", 0
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    opener = urllib.request.build_opener(SafeRedirectHandler())
    try:
        with opener.open(request, timeout=60) as response, part.open("wb") as output:
            validate_media_url(response.geturl())
            content_type = response.headers.get_content_type() or ""
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    advertised_size = int(content_length)
                except ValueError:
                    advertised_size = 0
                if advertised_size > max_bytes:
                    raise SkillError(
                        "MEDIA_TOO_LARGE",
                        "The advertised media size exceeds the configured limit",
                        advertised_bytes=advertised_size,
                        max_bytes=max_bytes,
                    )
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                if size + len(block) > max_bytes:
                    raise SkillError(
                        "MEDIA_TOO_LARGE",
                        "The media stream exceeded the configured limit",
                        max_bytes=max_bytes,
                    )
                if len(first) < 32:
                    first += block[: 32 - len(first)]
                output.write(block)
                digest.update(block)
                size += len(block)
        if len(first) < 12 or first[4:8] != b"ftyp":
            raise SkillError("INVALID_MP4", "Downloaded content does not have an MP4 ftyp header")
        os.replace(part, destination)
        return size, digest.hexdigest(), content_type
    except Exception:
        if part.exists():
            part.unlink()
        raise


def resolve(context: BrowserContext, page: Page, capture: dict[str, Any], share_url: str, codec: str) -> tuple[dict[str, Any], str]:
    parsed = browser_fetch_parse(page, share_url, capture.get("headers") or {})
    data = get_feed(context, parsed)
    feed = data.get("feedInfo") or {}
    return data, media_url(feed, codec)


def resolve_with_reauth(
    context: BrowserContext,
    page: Page,
    capture: dict[str, Any],
    share_url: str,
    codec: str,
    timeout: int,
    headless: bool,
) -> tuple[dict[str, Any], str, bool]:
    try:
        data, url = resolve(context, page, capture, share_url, codec)
        return data, url, False
    except SkillError as exc:
        if exc.code != "YUANBAO_AUTH_FAILED":
            raise
        if headless:
            raise SkillError(
                "YUANBAO_AUTH_FAILED",
                "The saved session expired; rerun without --headless to log in and retry automatically",
                http_status=exc.details.get("http_status", 401),
            ) from exc
        print(
            "SESSION_EXPIRED: clearing only the dedicated Yuanbao session; log in in the visible browser to retry",
            file=sys.stderr,
            flush=True,
        )
        clear_dedicated_yuanbao_session(context, page)
        refresh_capture_after_login(context, page, capture, timeout)
        try:
            data, url = resolve(context, page, capture, share_url, codec)
            return data, url, True
        except SkillError as retry_exc:
            if retry_exc.code == "YUANBAO_AUTH_FAILED":
                retry_exc.details["reauth_attempted"] = True
            raise


def run_doctor(args: argparse.Namespace, root: Path) -> int:
    installed = available_browsers()
    browser = select_browser(root, args.browser, required=False)
    profile = profile_for(root, browser, args.profile_dir) if browser else None
    executable = locate_browser(browser) if browser else None
    profile_exists = bool(profile and profile.exists())
    result: dict[str, Any] = {
        "ok": bool(installed),
        "skill_version": SKILL_VERSION,
        "available_browsers": list(installed),
        "selected_browser": browser,
        "browser_path": str(executable) if executable else None,
        "selection_required": browser is None,
        "profile_dir": str(profile) if profile else None,
        "profile_exists": profile_exists,
        "playwright": True,
        "logged_in": False if browser and not profile_exists else None,
    }
    if browser and executable and profile and profile_exists:
        try:
            with sync_playwright() as playwright:
                context = browser_context(playwright, profile, True, browser)
                result["logged_in"] = is_logged_in(context)
                context.close()
        except Exception as exc:
            result["profile_check"] = f"unavailable: {type(exc).__name__}"
    result["login_required"] = bool(browser and result["logged_in"] is not True)
    result["ready_for_download"] = bool(browser and executable and result["logged_in"] is True)
    emit(result)
    return 0 if result["ok"] else 1


def run_browser_command(args: argparse.Namespace, root: Path) -> int:
    share_url = validate_share_url(args.url) if args.command in {"resolve", "download"} else None
    browser = select_browser(root, args.browser)
    assert browser is not None
    profile = profile_for(root, browser, args.profile_dir)
    with sync_playwright() as playwright:
        context = browser_context(playwright, profile, args.headless, browser)
        try:
            if args.command == "login":
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(YUANBAO_ORIGIN, wait_until="domcontentloaded", timeout=60_000)
                if args.force:
                    if args.headless:
                        raise SkillError("LOGIN_REQUIRED", "Forced login requires a visible browser; remove --headless")
                    clear_dedicated_yuanbao_session(context, page)
                    page.goto(YUANBAO_ORIGIN, wait_until="domcontentloaded", timeout=60_000)
                wait_for_login(context, page, args.timeout)
                emit({"ok": True, "skill_version": SKILL_VERSION, "logged_in": True, "browser": browser, "profile_dir": str(profile), "forced": bool(args.force)})
                return 0
            page, capture = prepare_page(context, args.timeout, args.headless)
            data, url, reauthenticated = resolve_with_reauth(
                context, page, capture, share_url, args.codec, args.timeout, args.headless
            )
            feed = data.get("feedInfo") or {}
            base = {"ok": True, "skill_version": SKILL_VERSION, "share_url": share_url, "browser": browser, "reauthenticated": reauthenticated, "author": (data.get("authorInfo") or {}).get("nickname") or "", "title": feed.get("description") or "", "media_type": feed.get("mediaType"), "codec": args.codec}
            if args.command == "resolve":
                emit({**base, "downloadable": bool(url)})
                return 0
            output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else default_downloads()
            output_dir.mkdir(parents=True, exist_ok=True)
            destination = unique_path(output_dir, clean_filename(base["title"]))
            if not 1 <= args.max_mb <= 10240:
                raise SkillError("INVALID_SIZE_LIMIT", "--max-mb must be between 1 and 10240")
            size, sha256, content_type = download_video(url, destination, args.max_mb * 1024 * 1024)
            preview, preview_mode = ensure_preview_path(destination, share_url)
            emit({
                **base,
                "file_path": str(destination),
                "preview_path": str(preview),
                "preview_mode": preview_mode,
                "bytes": size,
                "sha256": sha256,
                "content_type": content_type,
                "verified_mp4_header": True,
            })
            return 0
        finally:
            context.close()


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--profile-dir", help="Dedicated browser profile directory")
    sub = cli.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--browser", choices=BROWSER_NAMES)
    login = sub.add_parser("login")
    login.add_argument("--browser", choices=BROWSER_NAMES)
    login.add_argument("--timeout", type=int, default=300)
    login.add_argument("--headless", action="store_true")
    login.add_argument("--force", action="store_true", help="Clear only the dedicated Yuanbao session before login")
    for name in ("resolve", "download"):
        command = sub.add_parser(name)
        command.add_argument("url")
        command.add_argument("--browser", choices=BROWSER_NAMES)
        command.add_argument("--codec", choices=("h264", "h265"), default="h264")
        command.add_argument("--timeout", type=int, default=300)
        command.add_argument("--headless", action="store_true")
        if name == "download":
            command.add_argument("--output-dir")
            command.add_argument("--max-mb", type=int, default=DEFAULT_MAX_BYTES // (1024 * 1024))
    return cli


def main() -> int:
    args = parser().parse_args()
    root = default_root()
    try:
        return run_doctor(args, root) if args.command == "doctor" else run_browser_command(args, root)
    except SkillError as exc:
        emit({"ok": False, "skill_version": SKILL_VERSION, "error": {"code": exc.code, "message": str(exc), **exc.details}})
        return 2
    except Exception as exc:
        emit({"ok": False, "skill_version": SKILL_VERSION, "error": {"code": "UNEXPECTED_ERROR", "message": f"{type(exc).__name__}: {exc}"}})
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
