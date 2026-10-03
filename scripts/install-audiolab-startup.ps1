$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $repoRoot 'START-AUDIOLAB.bat'
$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'Audiolab.lnk'

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcher
$shortcut.WorkingDirectory = $repoRoot
$shortcut.WindowStyle = 7
$shortcut.Description = 'Start Audiolab local AI audio studio'
$shortcut.Save()

Write-Host "Audiolab will now start automatically when you sign in to Windows." -ForegroundColor Green
Write-Host "Startup shortcut: $shortcutPath"
