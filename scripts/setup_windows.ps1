$ErrorActionPreference = "Stop"

python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip install git+https://github.com/AI4Bharat/IndicF5.git

Write-Host "IndicF5 installation complete."
Write-Host "If Hugging Face requires authentication, run: huggingface-cli login"
