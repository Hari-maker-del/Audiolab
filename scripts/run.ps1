$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Run .\scripts\setup_windows.ps1 first."
    exit 1
}
& .\.venv\Scripts\python.exe app\server.py
