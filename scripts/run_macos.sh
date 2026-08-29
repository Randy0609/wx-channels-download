#!/bin/zsh
set -u

skill_script_dir="${0:A:h}"
skill_python_script="${skill_script_dir}/yuanbao_channels.py"
typeset -a skill_python_candidates

if [[ -n "${WX_CHANNELS_PYTHON:-}" ]]; then
  skill_python_candidates+=("${WX_CHANNELS_PYTHON}")
fi

skill_python_candidates+=(
  "${HOME}/.wx-channels-download/runtime/bin/python"
  "${HOME}/.workbuddy/binaries/python/envs/default/bin/python"
)

system_python3="$(command -v python3 2>/dev/null || true)"
if [[ -n "${system_python3}" ]]; then
  skill_python_candidates+=("${system_python3}")
fi

for skill_python in "${skill_python_candidates[@]}"; do
  if [[ ! -x "${skill_python}" ]]; then
    continue
  fi
  if "${skill_python}" -c 'import sys, playwright; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    exec "${skill_python}" "${skill_python_script}" "$@"
  fi
done

print -r -- '{"ok":false,"skill_version":"1.1.0-randy.1","error":{"code":"PLAYWRIGHT_MISSING","message":"No Python 3.10+ runtime with Playwright was found. After dependency-install authorization, run scripts/setup_macos.sh."}}'
exit 2
