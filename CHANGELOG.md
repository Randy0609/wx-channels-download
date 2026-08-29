# Changelog

## 1.1.0-randy.1 - 2026-08-29

- Add native macOS runners and a Skill-only Playwright virtual environment.
- Honor `WX_CHANNELS_ROOT` in both setup and runtime so host-specific tests and deployments stay isolated.
- Reuse installed Chrome or Edge instead of downloading a Playwright browser.
- Add explicit `ready_for_download` and `login_required` doctor fields.
- Restrict browser profiles to the Skill-owned runtime root.
- Allowlist captured Yuanbao request headers and keep them in memory only.
- Enforce public HTTPS media URLs across redirects, an MP4 header check, a configurable size ceiling, SHA-256 output, and cleanup of partial files.
- Add preview-safe filenames without duplicating media bytes when hard links are available.
- Add Codex, DSH, and WorkBuddy installation guidance, CI, package validation, and security regression tests.

## 1.0.0 - upstream baseline

- Initial community package downloaded from SkillHub.
