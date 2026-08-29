#!/bin/zsh
set -u

if [[ "$(uname -s)" != "Darwin" ]]; then
  print -r -- '{"ok":false,"error":{"code":"UNSUPPORTED_PLATFORM","message":"setup_macos.sh only supports macOS."}}'
  exit 2
fi

skill_runtime_root="${WX_CHANNELS_ROOT:-${HOME}/.wx-channels-download}"
skill_runtime_dir="${skill_runtime_root}/runtime"
bootstrap_python="${WX_CHANNELS_BOOTSTRAP_PYTHON:-$(command -v python3 2>/dev/null || true)}"

if [[ -z "${bootstrap_python}" ]] || ! "${bootstrap_python}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
  print -r -- '{"ok":false,"error":{"code":"PYTHON_REQUIRED","message":"Python 3.10 or newer is required."}}'
  exit 2
fi

if ! mkdir -p "${skill_runtime_root}"; then
  print -r -- '{"ok":false,"error":{"code":"RUNTIME_DIR_FAILED","message":"Could not create the Skill-only runtime directory."}}'
  exit 3
fi

if ! "${bootstrap_python}" -m venv "${skill_runtime_dir}"; then
  print -r -- '{"ok":false,"error":{"code":"PYTHON_VENV_FAILED","message":"Could not create the Skill-only Python environment."}}'
  exit 3
fi

if ! "${skill_runtime_dir}/bin/python" -m pip install --disable-pip-version-check --upgrade 'playwright>=1.52,<2'; then
  print -r -- '{"ok":false,"error":{"code":"PLAYWRIGHT_INSTALL_FAILED","message":"Check PyPI/network access and retry."}}'
  exit 4
fi

print -r -- "{\"ok\":true,\"skill_version\":\"1.1.0-randy.1\",\"runtime_python\":\"${skill_runtime_dir}/bin/python\",\"browser_binary_downloaded\":false}"
