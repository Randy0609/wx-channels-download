---
name: wx-channels-download
description: Download and verify an authorized WeChat Channels (视频号) MP4 from an official weixin.qq.com/sph share link by using an isolated Tencent Yuanbao session in local Chrome or Edge. Use for download, metadata resolution, login recovery, or environment diagnosis; do not use for private, deleted, paywalled, or access-controlled media.
metadata:
  version: "1.1.0-randy.1"
  compatibility: "macOS or Windows; Python 3.10+ with Playwright; installed Chrome or Edge"
---

# WeChat Channels Download

Use only an official `https://weixin.qq.com/sph/` link supplied by the user. Keep authentication in this Skill's dedicated browser profile; never request or expose cookies, tokens, captured headers, normal browser profiles, or media URLs.

## Choose the platform runner

- macOS: `zsh scripts/run_macos.sh <command>`
- Windows: `powershell -ExecutionPolicy Bypass -File scripts/run.ps1 <command>`

The macOS runner searches, in order, `WX_CHANNELS_PYTHON`, the Skill-only runtime, WorkBuddy's managed runtime when present, and system Python. It uses the first Python 3.10+ runtime that already has Playwright. If none exists, explain the local dependency install and run `scripts/setup_macos.sh` only within the user's authorized setup task. Do not run `playwright install`; the Skill reuses installed Chrome or Edge.

## Workflow

1. Run `doctor`. Treat its fields separately:
   - `ok: true` means required local components were found.
   - `ready_for_download: true` means a browser is selected and the dedicated profile is logged in.
   - Neither field proves that a requested video was downloaded.
2. If no browser is selected, choose the only available browser automatically. If both Edge and Chrome are available and the user has not chosen, ask once, then persist the answer with `doctor --browser edge|chrome`.
3. If `login_required` is true, run visible `login --browser edge|chrome --timeout 300` and ask the user to complete Tencent Yuanbao login in the dedicated window. Wait for the command to finish.
4. Run `resolve` only when metadata or availability is requested. Do not report a saved file from `resolve`.
5. Run `download` for a requested save. H.264 is the compatibility default; use `--codec h265` only when requested. Use an explicit output directory when the user supplied one.
6. Report only verified output fields: `file_path`, `preview_path`, byte size, title, author, codec, content type, SHA-256, and `verified_mp4_header`. Use `preview_path` for Codex Desktop media embedding. If `ffprobe` is available, independently report duration, dimensions, frame rate, and audio/video codecs.

Example on macOS:

```bash
zsh scripts/run_macos.sh download \
  "https://weixin.qq.com/sph/..." \
  --browser chrome \
  --output-dir "/absolute/output/directory"
```

## Security and stopping rules

- Use only `~/.wx-channels-download/profiles/<browser>` or the legacy Skill-only Edge profile. Reject a custom profile outside that root; never point the script at Chrome or Edge's normal user-data directory.
- Captured authentication headers stay in memory, are allowlisted immediately, and are replayed only to the same-origin Yuanbao parse API. Never print, persist, or send them elsewhere.
- Media downloads must remain HTTPS. Reject embedded credentials, local hostnames, non-public IP literals, unsafe redirects, non-MP4 payloads, and streams larger than the configured limit (default 2048 MB).
- A visible command may recover one Yuanbao HTTP 401 by clearing only the selected dedicated session, waiting for login, and retrying the original link once. Stop after that retry.
- `login --force` clears only the dedicated Yuanbao cookies and web storage. Do not delete a whole profile unless the user explicitly requests a full reset.
- Keep the browser visible by default. Use `--headless` only after a successful visible download on that browser and machine.
- Download only content the user is authorized to access. Do not bypass private access, deletion, paywalls, DRM, CAPTCHA, or platform safety barriers.
- Do not claim completion from a health check, metadata result, task identifier, or partially written `.part` file. Completion requires a non-empty final MP4 plus the script's hash and MP4-header verification.

## Commands

- `doctor [--browser edge|chrome]`: Inspect prerequisites, saved selection, dedicated-profile login state, and readiness.
- `login [--browser edge|chrome] [--force] [--timeout 300]`: Open the isolated browser profile and wait for user login.
- `resolve <url> [--browser edge|chrome] [--codec h264|h265]`: Resolve metadata without saving media.
- `download <url> [--browser edge|chrome] [--codec h264|h265] [--output-dir PATH] [--max-mb N]`: Save and verify the MP4, then return a preview-safe path.

Read [references/troubleshooting.md](references/troubleshooting.md) after any nonzero exit or error JSON.
