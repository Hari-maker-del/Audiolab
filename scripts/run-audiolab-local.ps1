$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repoRoot 'backend'
$frontend = Join-Path $repoRoot 'frontend'
$venv = Join-Path $backend '.venv'

Write-Host '=== Audiolab Local-First Setup ===' -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python is not installed or is not on PATH. Install Python 3.11.x first.'
}

if (-not (Test-Path $venv)) {
    Write-Host 'Creating Python virtual environment...'
    python -m venv $venv
}

$python = Join-Path $venv 'Scripts\python.exe'
$pip = Join-Path $venv 'Scripts\pip.exe'

& $python -m pip install --upgrade pip
& $pip install -r (Join-Path $backend 'requirements.txt')

$envFile = Join-Path $backend '.env'
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)\s*=\s*(.*)\s*$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
        }
    }
} else {
    Write-Warning 'backend/.env was not found. If IndicF5 is gated, create it from backend/.env.example and add HF_TOKEN.'
}

Write-Host 'Starting FastAPI at http://127.0.0.1:8000 ...' -ForegroundColor Green
Start-Process -FilePath $python -ArgumentList '-m','uvicorn','server:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $backend

Start-Sleep -Seconds 2

Write-Host 'Starting Audiolab frontend at http://127.0.0.1:5500 ...' -ForegroundColor Green
Start-Process -FilePath $python -ArgumentList '-m','http.server','5500' -WorkingDirectory $frontend

Write-Host ''
Write-Host 'Audiolab is running locally:' -ForegroundColor Cyan
Write-Host '  UI:     http://127.0.0.1:5500'
Write-Host '  API:    http://127.0.0.1:8000/health'
Write-Host ''
Write-Host 'Close the two Python windows/processes when finished.' -ForegroundColor Yellow
Start-Process 'http://127.0.0.1:5500'
