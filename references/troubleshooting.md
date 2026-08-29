# Troubleshooting

## Error routing

- `PYTHON_REQUIRED`: Install Python 3.10+ from the official Python site, then retry platform setup. Do not install an unofficial runtime.
- `PLAYWRIGHT_MISSING`: On macOS, explain that `scripts/setup_macos.sh` creates `~/.wx-channels-download/runtime` and installs only the Playwright Python package. Run it only inside an authorized setup task. On Windows, rerun `scripts/run.ps1` so its Skill-only runtime setup can complete.
- `PLAYWRIGHT_INSTALL_FAILED` or `PLAYWRIGHT_SETUP_FAILED`: Check PyPI/network access. Do not run `playwright install`; this Skill uses the installed Chrome or Edge binary.
- `BROWSER_SELECTION_REQUIRED`: If exactly one supported browser is available, select it. If both are present, ask the user once and persist the answer with `doctor --browser <choice>`.
- `BROWSER_MISSING`: Report `available_browsers`. Use only official Chrome or Edge installation sources; do not acquire another browser silently.
- `UNSAFE_PROFILE_DIR`: Remove the custom profile override. The only allowed profiles are inside `~/.wx-channels-download/profiles/` or the legacy Skill-only Edge profile.
- `LOGIN_REQUIRED` or `LOGIN_TIMEOUT`: Run visible `login` and let the user authenticate in the dedicated window. Do not request cookies, tokens, QR screenshots, or normal browser data.
- `NO_CAPTURED_HEADERS`: Keep the dedicated Yuanbao window open briefly, interact with that page once if needed, then retry. Never copy headers from another profile.
- `YUANBAO_AUTH_FAILED`: A visible resolve/download clears only the dedicated Yuanbao session and retries once after login. If that retry fails, stop; use `login --force` only for a user-authorized session reset.
- `YUANBAO_PARSE_FAILED`: Confirm the official share link remains accessible and retry later. Yuanbao may be rate-limiting or may have changed its API.
- `WEIXIN_PARSE_FAILED` or `MEDIA_URL_MISSING`: The item may be private, deleted, expired, or unsupported. Do not attempt alternate private APIs or access bypasses.
- `UNSAFE_MEDIA_URL`: Stop. The resolved or redirected media URL was not a public HTTPS destination.
- `MEDIA_TOO_LARGE`: Report the configured byte limit. Increase `--max-mb` only when the user expects a larger authorized file; the hard maximum is 10240 MB.
- `INVALID_MP4`: The response was incomplete, expired, or not an MP4. The `.part` file is removed automatically; retry resolution rather than renaming it.

## Readiness versus completion

`doctor` is diagnostic only:

- `ok` confirms that a supported browser is installed.
- `ready_for_download` confirms browser selection plus a logged-in dedicated profile.
- `resolve` confirms metadata and a media candidate without saving it.
- Only `download` with a non-empty final `file_path`, SHA-256, and `verified_mp4_header: true` establishes local download completion.

If `profile_check` is unavailable, a running browser may be holding the dedicated profile. Close only that dedicated Skill window and retry; do not terminate the user's normal browser.

## Profile and secret boundaries

The saved browser selection lives at `%LOCALAPPDATA%\wx-channels-download\settings.json` on Windows or `~/.wx-channels-download/settings.json` on macOS. Sessions remain under the matching Skill root. Never inspect, print, upload, archive, or commit the dedicated profile, and never read Chrome or Edge's normal user-data directory.

The script filters request headers immediately to the Yuanbao fields needed for same-origin replay. It never writes captured headers to disk or includes them in result JSON. Final responses must omit cookies, media URLs, `generalToken`, `exportId`, and captured headers.

## Platform runners

- macOS: `scripts/run_macos.sh` selects an existing compatible Python runtime. `scripts/setup_macos.sh` is the explicit dependency-setup path and does not download a browser binary.
- Windows: `scripts/run.ps1` locates or creates the Skill-only runtime; `scripts/setup.ps1` is the diagnostic setup path.

The browser opens only while `login`, `resolve`, or `download` runs and closes afterward. The Skill creates no startup entry, scheduled task, service, extension, root certificate, or always-running background process.
