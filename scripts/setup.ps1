$ErrorActionPreference = "Stop"
$root = Join-Path $env:LOCALAPPDATA "wx-channels-download"
$venv = Join-Path $root "runtime"
$python = $null
foreach ($name in @("python", "py")) {
    $candidate = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $candidate) {
        continue
    }
    try {
        & $candidate.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $python = $candidate.Source
            break
        }
    } catch {
        continue
    }
}
if (-not $python) {
    Write-Error "PYTHON_REQUIRED: Python 3.10 or newer was not found." -ErrorAction Continue
    Write-Output "Install Python for Windows from https://www.python.org/downloads/windows/"
    Write-Output "Enable 'Add python.exe to PATH', reopen Codex, then retry the original video link."
    exit 2
}

New-Item -ItemType Directory -Force -Path $root | Out-Null
Write-Output "Creating Skill-only runtime: $venv"
& $python -m venv $venv
if ($LASTEXITCODE -ne 0) {
    Write-Error "PYTHON_VENV_FAILED: Could not create the Skill-only Python environment." -ErrorAction Continue
    exit 3
}
$venvPython = Join-Path $venv "Scripts\python.exe"
& $venvPython -m pip install --disable-pip-version-check --upgrade "playwright>=1.52,<2"
if ($LASTEXITCODE -ne 0) {
    Write-Error "PLAYWRIGHT_INSTALL_FAILED: Check the network connection and retry." -ErrorAction Continue
    exit 4
}
Write-Output "SETUP_COMPLETE: Playwright runtime ready at $venvPython"
Write-Output "The Skill uses installed Edge or Chrome directly; playwright install is not required."
