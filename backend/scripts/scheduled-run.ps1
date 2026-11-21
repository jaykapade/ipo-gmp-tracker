<#
.SYNOPSIS
    Scheduled IPO Checker job: scrape -> analyse -> AI research -> PDF -> email,
    then the open-IPO digest to confirmed subscribers.

.DESCRIPTION
    Meant for Windows Task Scheduler (see backend/README.md, "Scheduling").
    Runs from the backend folder regardless of the task's start directory and
    appends all output to backend/logs/scheduled-YYYY-MM-DD.log.

    Examples:
        scheduled-run.ps1 -DryRun        # everything except sending the email
        scheduled-run.ps1 -NoResearch    # skip AI research
        scheduled-run.ps1 -NoNotify      # skip the subscriber digest
    Other settings (screen, max research age) come from backend/.env.local.

    The claude-code provider uses your Claude login, so the task must run as
    your own Windows user (not SYSTEM).
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$NoResearch,
    [switch]$NoNotify
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

$base = @('run', 'python', '-m', 'src.main')
$report = $base + @('run', '--email')
if (-not $NoResearch) { $report += '--research' }
if ($DryRun) { $report += '--dry-run' }
$jobs = @(, $report)
if (-not $NoNotify) {
    $notify = $base + @('notify')
    if ($DryRun) { $notify += '--dry-run' }
    $jobs += , $notify
}

# uv's "requires-python" notice and Python logging go to stderr. In Windows
# PowerShell 5.1 redirected stderr lines become error records, which 'Stop'
# would turn into a fatal error, so relax it while the job runs.
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$code = 0
foreach ($arguments in $jobs) {
    "=== {0:yyyy-MM-dd HH:mm:ss} uv {1}" -f (Get-Date), ($arguments -join ' ') |
        Out-File -FilePath $log -Append -Encoding utf8
    & $uv @arguments *>&1 | ForEach-Object { "$_" } |
        Out-File -FilePath $log -Append -Encoding utf8
    "=== exit $LASTEXITCODE" | Out-File -FilePath $log -Append -Encoding utf8
    if ($LASTEXITCODE -ne 0) { $code = $LASTEXITCODE }
}

exit $code
