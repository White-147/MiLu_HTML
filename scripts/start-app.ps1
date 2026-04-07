param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8088,
    [int]$TimeoutSec = 120
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$env:MILU_WORKING_DIR = $repoRoot
$env:MILU_SECRET_DIR = Join-Path $repoRoot ".secret"

$logDir = Join-Path $repoRoot "logs"
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$logFile = Join-Path $logDir "uvicorn-$ts.log"

$py = "D:\soft\program\Python\Python311\python.exe"
$url = "http://$BindHost`:$Port/api/healthz"

try {
    $existing = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2
    if ($existing.StatusCode -eq 200) {
        Write-Host "App already running: http://$BindHost`:$Port"
        exit 0
    }
} catch {
}

Write-Host "Starting app on http://$BindHost`:$Port ..."
Write-Host "Log file: $logFile"

$launchCmd = @"
Set-Location '$repoRoot'
`$env:MILU_WORKING_DIR='$repoRoot'
`$env:MILU_SECRET_DIR='$($env:MILU_SECRET_DIR)'
& '$py' -m uvicorn copaw.app._app:app --host $BindHost --port $Port *> '$logFile'
"@
$proc = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile","-WindowStyle","Hidden","-Command",$launchCmd -WorkingDirectory $repoRoot -PassThru

$deadline = (Get-Date).AddSeconds($TimeoutSec)
$ready = $false

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 1
    if ($proc.HasExited) {
        Write-Host "App process exited early (code=$($proc.ExitCode))."
        break
    }
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
    }
}

if ($ready) {
    Write-Host "App is ready: http://$BindHost`:$Port"
    Write-Host "PID: $($proc.Id)"
    exit 0
}

Write-Host "Startup timeout after $TimeoutSec seconds."
if (Test-Path $logFile) {
    Write-Host "Last 80 log lines:"
    Get-Content $logFile -Tail 80
}

exit 1
