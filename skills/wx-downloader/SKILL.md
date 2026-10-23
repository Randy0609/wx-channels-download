---
name: wx-downloader
description: 使用 wx-downloader 下载用户提供的微信视频号官方分享链接，处理腾讯元宝登录，并核验本地 MP4。适用于保存视频号视频、批量下载和下载失败排查；不用于公众号文章、直播或任意视频直链。
metadata:
  version: "1.0.0"
  tested_cli: "wx-downloader 0.1.2"
  tested_platform: "macOS Apple Silicon"
---

# 视频号下载与验证

将用户有权保存的 `https://weixin.qq.com/sph/...` 分享视频下载到本机，返回可点击文件和媒体预览。使用 [QinGeneral/wx-downloader](https://github.com/QinGeneral/wx-downloader)；本技能提供操作说明和独立媒体校验脚本，不包含下载器源码。

## 检查与安装

先检查命令；已安装且可用时直接复用：

```bash
wx-downloader --version
wx-downloader download --help
wx-downloader status
```

`status` 只反映本地保存状态，不能证明元宝服务端仍接受该登录。普通下载可直接执行，缺少本地凭据时 CLI 会打开登录窗口。

缺少命令且任务授权覆盖安装时，使用官方 PyPI 和独立环境。本次验证过的版本是 `0.1.2`：

```bash
uv tool install --default-index https://pypi.org/simple wx-downloader==0.1.2
```

需要 Python 3.10+ 和已安装的 Chrome。macOS 自带 `python3` 可能是 3.9；先检查版本，已有合适解释器时通过 `uv tool install --python /absolute/path/to/python3 ...` 指定。不要把某台电脑的运行时路径写成通用要求。

没有 uv 时，可用已核对版本的 Python 创建独立 venv，在其中运行 `python -m pip install --index-url https://pypi.org/simple wx-downloader==0.1.2`，随后使用该 venv 的命令。不要直接向系统 Python 安装依赖。

元宝登录复用本机 Chrome，无需为已有 Chrome 下载 Playwright Chromium，也无需安装证书或调整系统代理。只有用户另行选择 Chromium 时，才按下载器官方文档补装浏览器。

## 下载

用用户实际提供的链接替换示例中的 `SHARE_ID`。默认保存到下载目录，用户指定位置时使用其位置：

```bash
wx-downloader download 'https://weixin.qq.com/sph/SHARE_ID' \
  --output "$HOME/Downloads/wx-channels" --quality h264 --json
```

默认 H.264 便于预览；用户明确需要 H.265 时改为 `--quality h265`。编码偏好不代表原始画质，也不保证实际输出编码；以媒体检查为准。临时目录和质量用命令参数指定，不无故修改持久配置。

首次登录由用户在工具打开的元宝窗口中扫码或完成手机号验证。告知用户当前正在等待登录，保持任务继续；不要索取 Cookie、token、验证码或登录文件。

无人值守或只验证已有登录时可加 `--no-login`。需要主动重新登录时：

```bash
wx-downloader login --browser chrome --timeout 300
```

stdout JSON 包含 `summary` 和逐项 `results`，进度在 stderr。检查退出码和每项 `status`、`path`、`bytes` 或 `error`。`downloaded` 表示已保存；`skipped` 仅表示匹配到本地记录和大小，两者都继续核验文件；`failed` 不得称成功。

批量下载可传多个链接或 `--input links.json`，例如：

```json
{"links": [{"url": "https://weixin.qq.com/sph/SHARE_ID"}]}
```

输入应是 JSON，不是每行一个链接的普通文本。混合结果要逐项交付，不把部分成功说成全部成功。

## 验证并交付

使用 CLI 返回的最终 `path`，不要猜文件名。将以下路径替换为本技能目录和实际视频路径，`--expected-bytes` 使用 CLI 返回的 `bytes`，示例数字不是固定值：

```bash
python3 /path/to/wx-downloader/scripts/verify_media.py '/absolute/path/video.mp4' \
  --expected-bytes 123456 --full-decode
```

脚本核验非空最终 MP4、大小、MP4 文件头和 SHA-256；有 `ffprobe` 时读取时长、尺寸及音视频编码。`--full-decode` 使用 FFmpeg 完整解码所有音视频流，失败返回非零退出码。SHA-256 是本地文件标识，不能单独证明远端来源或内容一致。

`ffprobe` / `ffmpeg` 须能在 PATH 中找到。缺少工具时只交付实际完成的验证层级：不加 `--full-decode` 可做基础核验，`probe.status=unavailable` 或 `full_decode.status=not_requested` 不能称完整解码通过；仅 `full_decode.status=passed` 才能这样报告。不得为了补工具擅自更改系统安全或网络设置。

最终回复简短包含标题、文件链接、实测时长/大小/尺寸及验证范围。缺失数据不补成零。Codex Desktop 使用本地绝对路径嵌入媒体：

```markdown
[下载视频](/absolute/path/video.mp4)

![视频预览](/absolute/path/video.mp4)
```

## 失败处理与边界

- 明确登录过期或认证拒绝：由用户重新登录，再重试原链接一次；仍失败则报告真实错误，停止认证循环。401 不能直接推断为链接失效。
- 网络超时、429 或 5xx：保留 CLI 已有的有限重试结果，不在外层无限重试；不改代理、TUN 或路由来试错。
- 同名文件存在且无匹配记录：保留原文件，优先用新输出目录，不自动覆盖或删除。视频已保存但记录写入失败时，先核验成品，不盲目重复下载。
- 登录超时或窗口关闭：没有下载成功；不把“安装完成”“已登录”或 `.part` 文件说成下载完成。
- 私有、删除、付费、DRM、验证码或平台安全限制：不尝试绕过。不把工具层访问拒绝解释为需要用户换账号或提供凭据。
- 凭据仅由 CLI 在独立登录流程中管理。不要读取、输出或上传 `auth.json`、Cookie、请求头、storage state、日常浏览器 profile 或真实媒体直链；不将视频和认证缓存打包到技能或 GitHub。

2026-10-23 已在 macOS Apple Silicon + Chrome + CLI `0.1.2` 上完成真实下载及完整解码。其他设备、平台和未来接口状态需要分别验证。安装、登录、文件保存、媒体完整性和用户观看体验是不同的验收层级。
