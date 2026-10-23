# wx-channels-download

[![Validate Skill](https://github.com/Randy0609/wx-channels-download/actions/workflows/validate.yml/badge.svg)](https://github.com/Randy0609/wx-channels-download/actions/workflows/validate.yml)

视频号链接下载 Skill。输入用户有权访问的官方 `https://weixin.qq.com/sph/...` 分享链接，通过本机隔离的腾讯元宝浏览器会话解析、下载并校验 MP4。

这是一个可被 Codex、DeepSeek Harness（DSH）和 WorkBuddy 共用的文件夹式 Skill。仓库根目录直接包含 `SKILL.md`，GitHub Release 另提供不带 Git 历史的安装 ZIP。

## 基于 wx-downloader 的独立技能

新增 [skills/wx-downloader/SKILL.md](https://github.com/Randy0609/wx-channels-download/blob/main/skills/wx-downloader/SKILL.md)：使用 [QinGeneral/wx-downloader](https://github.com/QinGeneral/wx-downloader) 解析分享链接并下载，附本地文件、SHA-256、ffprobe 和完整 FFmpeg 解码校验。已在 macOS Apple Silicon、Chrome、CLI `0.1.2` 上完成真实下载验证。

这个子技能调用外部 CLI，不复制其下载器源码，也不要求启动仓库根目录的下载服务。需要用户在独立元宝窗口完成登录，无需安装证书或调整系统代理。下面的根目录安全实现、runner 命令和旧版 Release ZIP 说明仅对应原有 `wx-channels-download` 技能；子技能的操作以自身 `SKILL.md` 为准。

安装到 Codex 的示例（目标目录已存在时先比较，避免覆盖）：

```bash
git clone --depth 1 https://github.com/Randy0609/wx-channels-download.git
mkdir -p "$HOME/.codex/skills"
test ! -e "$HOME/.codex/skills/wx-downloader" && \
  cp -R wx-channels-download/skills/wx-downloader "$HOME/.codex/skills/wx-downloader"
uv tool install --default-index https://pypi.org/simple wx-downloader==0.1.2
```

将整个 `wx-downloader/` 子目录复制到其他客户端实际使用的技能目录也可；客户端发现和实际执行需要分别检查。现有 `wx-channels-download-v1.1.0-randy.1.zip` 不包含这个新增子技能。

调用示例：`用 $wx-downloader 下载这个视频号分享链接，并验证音视频完整性。`

附带校验脚本只核验本地成品，不读取登录凭据、不访问网络。缺少 ffprobe 或未执行完整解码时，会明确保留未验证状态。子技能的原始说明和校验代码采用子目录内 [LICENSE](https://github.com/Randy0609/wx-channels-download/blob/main/skills/wx-downloader/LICENSE)；外部 CLI 仍遵循自己的许可。

## 安全边界

- 只接受用户提供的官方 `weixin.qq.com/sph` HTTPS 链接。
- 登录状态仅保存在 `~/.wx-channels-download/` 下的 Skill 专用浏览器 profile，不读取日常 Chrome / Edge profile。
- Cookie、token、捕获的请求头和媒体真实 URL 不输出、不写入仓库、不应出现在交付回复中。
- 下载器拒绝非 HTTPS、本地/私有 IP、嵌入账号密码的 URL、不安全重定向、非 MP4 载荷和超过限制的流。
- 不绕过私有访问、付费、删除、DRM、验证码或平台安全措施。仅下载你有权保存的内容。

## 系统要求

- macOS 或 Windows
- Python 3.10+
- 本机已安装 Google Chrome 或 Microsoft Edge
- Python Playwright `>=1.52,<2`

Skill 直接复用本机已安装的 Chrome / Edge，不需要执行 `playwright install`，也不会额外下载浏览器二进制文件。

## 安装

下列三个目录是默认约定。如果你的客户端配置了自定义 Skill 目录，请以客户端当前配置为准。

### Codex

```bash
git clone --depth 1 https://github.com/Randy0609/wx-channels-download.git \
  ~/.codex/skills/wx-channels-download
```

重启 Codex 或刷新 Skills 列表，然后用官方分享链接调用 `$wx-channels-download`。

### DeepSeek Harness（DSH）

```bash
git clone --depth 1 https://github.com/Randy0609/wx-channels-download.git \
  ~/.dsh/skills/wx-channels-download
```

重启 DSH 或执行当前版本的 Skill catalog 刷新。“文件已复制”不等于“DSH 已发现并成功调用”，首次安装后应运行一次 `doctor` 做现场验收。

### WorkBuddy

```bash
git clone --depth 1 https://github.com/Randy0609/wx-channels-download.git \
  ~/.workbuddy/skills/wx-channels-download
```

重启 WorkBuddy 或刷新 Skill 列表。如果已存在旧的 `wx-video-download` 副本，不要保留两个同时激活的重复 Skill；先备份旧副本，再做单副本迁移。

### 从 Release ZIP 安装

不使用 Git 时，从 [Releases](https://github.com/Randy0609/wx-channels-download/releases) 下载 `wx-channels-download-v1.1.0-randy.1.zip` 和 `SHA256SUMS.txt`，核对 SHA-256 后，将 ZIP 内的 `wx-channels-download/` 放入对应的 Skills 目录。

## 首次设置与诊断

macOS：

```bash
cd ~/.codex/skills/wx-channels-download
zsh scripts/setup_macos.sh
zsh scripts/run_macos.sh doctor
```

Windows PowerShell：

```powershell
cd "$HOME\.codex\skills\wx-channels-download"
powershell -ExecutionPolicy Bypass -File scripts\run.ps1 doctor
```

macOS 的 `setup_macos.sh` 会在 `~/.wx-channels-download/runtime/` 创建隔离 venv，并仅安装 Playwright Python 包。Windows runner 在找不到可用 Playwright 时会使用同等的 Skill 专用 runtime。

`doctor` 的证据含义要分开看：

- `ok: true`：本机找到了支持的浏览器。
- `ready_for_download: true`：已选浏览器，专用 profile 也检测到登录状态。
- 两者都不代表某个视频已经下载。

## 命令

macOS runner：

```bash
zsh scripts/run_macos.sh doctor [--browser chrome|edge]
zsh scripts/run_macos.sh login [--browser chrome|edge] [--timeout 300]
zsh scripts/run_macos.sh resolve "https://weixin.qq.com/sph/..." [--codec h264|h265]
zsh scripts/run_macos.sh download "https://weixin.qq.com/sph/..." \
  [--browser chrome|edge] [--codec h264|h265] [--output-dir /absolute/path]
```

Windows 将 `zsh scripts/run_macos.sh` 换成：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run.ps1
```

具体错误路由见 [references/troubleshooting.md](references/troubleshooting.md)。

## 更新

如果是 Git 安装：

```bash
git -C ~/.codex/skills/wx-channels-download pull --ff-only
```

对 DSH / WorkBuddy 把路径替换为对应安装目录。更新后重启或刷新 Skill catalog，再运行 `doctor`。

## 版本与校验边界

- 当前版本：`1.1.0-randy.1`
- 自动 CI：校验包结构、版本一致性、Python 语法、URL / profile / header / 媒体安全回归、macOS shell 语法和 Release ZIP 结构。
- CI 不使用私人登录会话，因此不声称它证明视频号远程解析永久可用。
- 每次实际下载的完成标准是：非空最终 MP4、SHA-256、`verified_mp4_header: true`；如果本机有 `ffprobe`，应再做独立音视频流检查。

## 来源与许可

本项目是 SkillHub 社区包 `@user_2b46b0cf/wx-video-download` v1.0.0 的 Randy 维护版，加入了 macOS 运行器、隔离 runtime、更严格的凭据/profile/下载边界、校验字段、测试和三端安装文档。

上游存档未附带可确认的软件许可证。本仓库不会把上游派生内容擅自重新标记为 MIT 或其他开源许可。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [LICENSE-RANDY-ADDITIONS.md](LICENSE-RANDY-ADDITIONS.md)。
