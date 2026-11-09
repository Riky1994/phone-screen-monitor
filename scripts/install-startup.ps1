# PhoneDeck 安装开机自启：在「启动」文件夹放一个快捷方式，登录后静默启动
$ErrorActionPreference = 'Stop'
try {
    $here = Split-Path -Parent $PSScriptRoot
    $startup = [Environment]::GetFolderPath('Startup')
    $lnk = Join-Path $startup 'PhoneDeck.lnk'
    $wscript = Join-Path $env:SystemRoot 'System32\wscript.exe'
    $vbs = Join-Path $here 'autostart.vbs'

    if (-not (Test-Path $vbs)) { throw "找不到 autostart.vbs：$vbs" }

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($lnk)
    $shortcut.TargetPath = $wscript
    $shortcut.Arguments = '"' + $vbs + '"'
    $shortcut.WorkingDirectory = $here
    $shortcut.WindowStyle = 7
    $shortcut.Description = 'PhoneDeck - phone performance dashboard'
    $shortcut.Save()

    Write-Host ""
    Write-Host "  已安装开机自启。" -ForegroundColor Green
    Write-Host "  $lnk" -ForegroundColor DarkGray
    Write-Host "  下次开机登录后，服务会在后台自动启动（不弹窗口）。" -ForegroundColor DarkGray
    exit 0
} catch {
    Write-Host ""
    Write-Host "  [失败] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
