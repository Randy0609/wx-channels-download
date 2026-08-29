param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "yuanbao_channels.py"
$setupPath = Join-Path $PSScriptRoot "setup.ps1"
$localPython = Join-Path $env:LOCALAPPDATA "wx-channels-download\runtime\Scripts\python.exe"
$candidates = @(
    $env:WX_CHANNELS_PYTHON,
    $localPython,
    (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "python",
    "py"
) | Where-Object { $_ }

function Find-PlaywrightPython {
    foreach ($candidate in $candidates) {
        try {
            & $candidate -c "import playwright" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        } catch {
            continue
        }
    }
    return $null
}

$python = Find-PlaywrightPython
if (-not $python) {
    Write-Output "PLAYWRIGHT_SETUP: creating a Skill-only Python runtime; no browser binary will be downloaded."
    & $setupPath
    $python = Find-PlaywrightPython
    if (-not $python) {
        Write-Error "PLAYWRIGHT_SETUP_FAILED: Playwright is still unavailable after setup."
        exit 2
    }
}

& $python $scriptPath @CommandArgs
exit $LASTEXITCODE
