$ErrorActionPreference = "Stop"

python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip install git+https://github.com/AI4Bharat/IndicF5.git

Write-Host ""
Write-Host "IndicF5 installation complete."
Write-Host "If Hugging Face requests authentication, run: huggingface-cli login"
Write-Host "Then run .\scripts\run.ps1"
