<#
.SYNOPSIS
    Scheduled IPO Checker job: scrape -> analyse -> AI research -> PDF -> email.

.DESCRIPTION
    Meant for Windows Task Scheduler (see backend/README.md, "Scheduling").
    Runs from the backend folder regardless of the task's start directory and
    appends all output to backend/logs/scheduled-YYYY-MM-DD.log.

    Examples:
        scheduled-run.ps1 -DryRun        # everything except sending the email
        scheduled-run.ps1 -NoResearch    # skip AI research
    Other settings (screen, max research age) come from backend/.env.local.

    The claude-code provider uses your Claude login, so the task must run as
    your own Windows user (not SYSTEM).
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$NoResearch
)

$ErrorActionPreference = 'Stop'
$backend = Split-Path -Parent $PSScriptRoot
Set-Location $backend

$logDir = Join-Path $backend 'logs'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("scheduled-{0:yyyy-MM-dd}.log" -f (Get-Date))

$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
    $candidate = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
    if (Test-Path $candidate) { $uv = $candidate } else { throw 'uv not found on PATH' }
}

$arguments = @('run', 'python', '-m', 'src.main', 'run', '--email')
if (-not $NoResearch) { $arguments += '--research' }
if ($DryRun) { $arguments += '--dry-run' }

"=== {0:yyyy-MM-dd HH:mm:ss} uv {1}" -f (Get-Date), ($arguments -join ' ') |
    Out-File -FilePath $log -Append -Encoding utf8

# uv's "requires-python" notice and Python logging go to stderr. In Windows
# PowerShell 5.1 redirected stderr lines become error records, which 'Stop'
# would turn into a fatal error, so relax it while the job runs.
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
& $uv @arguments *>&1 | ForEach-Object { "$_" } |
    Out-File -FilePath $log -Append -Encoding utf8
$code = $LASTEXITCODE

"=== exit $code" | Out-File -FilePath $log -Append -Encoding utf8
exit $code
