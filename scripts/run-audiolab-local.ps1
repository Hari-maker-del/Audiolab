$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repoRoot 'backend'
$frontend = Join-Path $repoRoot 'frontend'
$venv = Join-Path $backend '.venv'
$python = Join-Path $venv 'Scripts\python.exe'

Write-Host '=== Audiolab Local ===' -ForegroundColor Cyan

if (-not (Test-Path $python)) {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python 3.11 is not installed or not on PATH.' }
    Write-Host 'First-time setup: creating virtual environment...' -ForegroundColor Yellow
    python -m venv $venv
    & $python -m pip install --upgrade pip
    & $python -m pip install -r (Join-Path $backend 'requirements.txt')
}

# Only install dependencies on first setup. This keeps normal startup fast.
$marker = Join-Path $backend '.audiolab_setup_complete'
if (-not (Test-Path $marker)) {
    Write-Host 'First-time setup: installing backend dependencies...' -ForegroundColor Yellow
    & $python -m pip install -r (Join-Path $backend 'requirements.txt')
    New-Item -ItemType File -Path $marker -Force | Out-Null
}

$envFile = Join-Path $backend '.env'
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)\s*=\s*(.*)\s*$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
        }
    }
}

# Avoid duplicate servers if Audiolab is already running.
$api = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
$web = Get-NetTCPConnection -LocalPort 5500 -State Listen -ErrorAction SilentlyContinue

if (-not $api) {
    Start-Process -FilePath $python -ArgumentList '-m','uvicorn','server:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $backend -WindowStyle Minimized
}

if (-not $web) {
    Start-Process -FilePath $python -ArgumentList '-m','http.server','5500' -WorkingDirectory $frontend -WindowStyle Minimized
}

Start-Sleep -Seconds 2
Start-Process 'http://127.0.0.1:5500'
Write-Host 'Audiolab is ready: http://127.0.0.1:5500' -ForegroundColor Green
Write-Host 'API: http://127.0.0.1:8000/health' -ForegroundColor Green
