$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
if (!(Test-Path $VenvPython)) {
    throw "Audiolab's backend virtual environment was not found. Run START-AUDIOLAB.bat once, then rerun this script."
}

Write-Host "Installing OpenVoice code and optional dependencies into Audiolab's backend environment..."
& $VenvPython -m pip install --no-deps "git+https://github.com/myshell-ai/OpenVoice.git"
if ($LASTEXITCODE -ne 0) { throw "Could not install the OpenVoice package." }

& $VenvPython -m pip install -r (Join-Path $RepoRoot "backend\requirements-voice-conversion.txt")
if ($LASTEXITCODE -ne 0) { throw "Could not install OpenVoice's optional dependencies." }

$ModelRoot = Join-Path $RepoRoot "backend\models\openvoice_v1"
$ExpectedConverter = Join-Path $ModelRoot "checkpoints\converter"
$ExpectedConfig = Join-Path $ExpectedConverter "config.json"
$ExpectedCheckpoint = Join-Path $ExpectedConverter "checkpoint.pth"

if (!(Test-Path $ExpectedConfig) -or !(Test-Path $ExpectedCheckpoint)) {
    New-Item -ItemType Directory -Force -Path $ModelRoot | Out-Null
    $ZipPath = Join-Path $env:TEMP "audiolab-openvoice-v1-checkpoints.zip"
    $CheckpointUrl = "https://myshell-public-repo-host.s3.amazonaws.com/openvoice/checkpoints_1226.zip"
    Write-Host "Downloading official OpenVoice V1 checkpoints. This is a large model download and requires internet."
    Invoke-WebRequest -Uri $CheckpointUrl -OutFile $ZipPath
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $ModelRoot -Force
    Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue

    if (!(Test-Path $ExpectedConfig) -or !(Test-Path $ExpectedCheckpoint)) {
        $FoundConfig = Get-ChildItem -Path $ModelRoot -Recurse -File -Filter "config.json" |
            Where-Object { $_.Directory.Name -eq "converter" } |
            Select-Object -First 1

        if ($FoundConfig) {
            New-Item -ItemType Directory -Force -Path $ExpectedConverter | Out-Null
            Copy-Item -Path (Join-Path $FoundConfig.Directory.FullName "*") -Destination $ExpectedConverter -Recurse -Force
        }
    }
}

if (!(Test-Path $ExpectedConfig) -or !(Test-Path $ExpectedCheckpoint)) {
    throw "The checkpoint archive did not contain checkpoints\converter\config.json and checkpoint.pth. Inspect the extracted folder before retrying."
}

Write-Host "Checking imports..."
& $VenvPython -c "from openvoice.api import ToneColorConverter; import wavmark; print('OpenVoice imports OK')"
if ($LASTEXITCODE -ne 0) { throw "OpenVoice import check failed. Check the error above." }

Write-Host ""
Write-Host "OpenVoice V1 conversion setup is ready."
Write-Host "Restart Audiolab and open Studio. Model weights are stored locally under backend\models\openvoice_v1."
Write-Host "Voice conversion runs on your local device. CPU conversion can be slow; CUDA is used when available."
