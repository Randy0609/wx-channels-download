# Third-party notices and provenance

This repository is a maintained derivative of the following SkillHub community package:

- Canonical name: `@user_2b46b0cf/wx-video-download`
- Slug: `wx-video-download`
- Upstream version: `1.0.0`
- SkillHub page: <https://api.skillhub.cn/user_2b46b0cf/wx-video-download>
- Download endpoint used for the archived baseline: <https://lightmake.site/api/v1/download?slug=wx-video-download>
- SHA-256 of the downloaded upstream ZIP: `27a0d6f8b9530b94de6954552f12d9f83cf7e7bff4663e5c765f4173e53e520d`
- Package metadata source type: `community`
- Package metadata owner: `user_2b46b0cf`

The downloaded upstream archive did not contain a `LICENSE`, `COPYING`, or equivalent license-grant file, and the package metadata did not declare a license. The repository therefore makes no claim that the upstream-derived material is distributed under MIT or any other OSI-approved license.

Files containing upstream-derived material include, at minimum, `SKILL.md`, `_meta.json`, `agents/openai.yaml`, `references/troubleshooting.md`, `scripts/run.ps1`, `scripts/setup.ps1`, and `scripts/yuanbao_channels.py`. These files contain later Randy-maintained revisions, but those revisions do not erase the upstream provenance or supply a missing upstream license grant.

Clearly original Randy-maintained additions include the macOS launch/setup scripts, repository documentation, CI workflow, package builder, and tests. The license grant for those original additions is scoped in `LICENSE-RANDY-ADDITIONS.md` and does not extend to upstream-derived material.

If the upstream author publishes license terms, or if documented redistribution authorization becomes available, update this notice before changing the repository-wide license status.

## Optional wx-downloader CLI skill

`skills/wx-downloader/` contains independently authored workflow instructions,
UI metadata and a local media verifier. It invokes the separately installed
[QinGeneral/wx-downloader](https://github.com/QinGeneral/wx-downloader) CLI and
does not vendor that project's source code or distribution. The CLI's license
and dependency terms remain those of its upstream project. The original files
within this subdirectory are covered by their own `LICENSE`.
