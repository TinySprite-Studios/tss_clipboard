$ErrorActionPreference = 'Stop'

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$startupDir = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupDir 'TSS Clipboard.lnk'
$exePath = Join-Path $projectDir 'dist\TSS-Clipboard.exe'
$batPath = Join-Path $projectDir 'start_clipboard.bat'

if (Test-Path $exePath) {
    $targetPath = $exePath
} elseif (Test-Path $batPath) {
    $targetPath = $batPath
} else {
    throw "Missing launcher. Expected $exePath or $batPath"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $projectDir
$shortcut.WindowStyle = 7
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,44"
$shortcut.Save()

Write-Host "Startup shortcut created: $shortcutPath"
