# PhoneDeck 一键部署（在新电脑上第一次运行时用）
# 用法：在此文件夹里右键 setup.ps1 ->「使用 PowerShell 运行」，或：
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1

param(
    [switch]$SkipFirewall,   # 跳过防火墙放行（手机将无法访问）
    [switch]$SkipShortcut,   # 跳过桌面快捷方式
    [switch]$NoStart         # 只做检查，不启动
)

$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$port = 8787

Write-Host ""
Write-Host "  PhoneDeck - 手机屏监控电脑性能" -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor DarkGray
Write-Host ""

# ---------- 1. 找 Python ----------
$pyw = $null
$runtimeRoot = Join-Path $env:USERPROFILE ".dsh\dsh-runtimes"
if (Test-Path $runtimeRoot) {
    $pyw = Get-ChildItem -Path $runtimeRoot -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName "dependencies\python\pythonw.exe" } |
        Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $pyw) {
    foreach ($name in @("pythonw.exe", "python.exe")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            $sibling = Join-Path (Split-Path $cmd.Source) "pythonw.exe"
            $pyw = if (Test-Path $sibling) { $sibling } else { $cmd.Source }
            break
        }
    }
}
if (-not $pyw) {
    $pyLauncher = Get-Command "pyw.exe" -ErrorAction SilentlyContinue
    if ($pyLauncher) { $pyw = $pyLauncher.Source }
}
if (-not $pyw) {
    Write-Host "  [失败] 没找到 Python。" -ForegroundColor Red
    Write-Host "  请安装 Python 3.9+（安装时勾选 Add Python to PATH），然后重新运行本脚本。" -ForegroundColor Yellow
    Read-Host "按回车退出"
    exit 1
}
Write-Host "  Python : $pyw" -ForegroundColor DarkGray

# ---------- 2. 依赖检查（psutil 已内置在 libs/） ----------
$pyExe = $pyw -replace 'pythonw\.exe$', 'python.exe'
if (-not (Test-Path $pyExe)) { $pyExe = $pyw }
$check = & $pyExe -c "import sys; sys.path.insert(0, r'$root\libs'); import psutil; print('psutil', psutil.__version__)" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [失败] psutil 不可用：$check" -ForegroundColor Red
    Write-Host "  如果是 32 位 Python 或非 x64 平台，请先执行：" -ForegroundColor Yellow
    Write-Host "    `"$pyExe`" -m pip install --target `"$root\libs`" psutil" -ForegroundColor Yellow
    Read-Host "按回车退出"
    exit 1
}
Write-Host "  依赖   : $check" -ForegroundColor DarkGray

# ---------- 3. 桌面快捷方式 ----------
if (-not $SkipShortcut) {
    try {
        $desk = [Environment]::GetFolderPath('Desktop')
        $lnk = Join-Path $desk "手机屏监控电脑性能.lnk"
        $ws = New-Object -ComObject WScript.Shell
        $sc = $ws.CreateShortcut($lnk)
        $sc.TargetPath = Join-Path $root "启动看板.bat"
        $sc.WorkingDirectory = $root
        $icon = Join-Path $root "app.ico"
        $sc.IconLocation = if (Test-Path $icon) { "$icon,0" } else { "C:\Windows\System32\imageres.dll,77" }
        $sc.Description = "手机屏监控电脑性能 - 一键启动看板"
        $sc.Save()
        Write-Host "  快捷方式: $lnk" -ForegroundColor Green
    } catch {
        Write-Host "  [警告] 桌面快捷方式创建失败：$($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# ---------- 4. 防火墙（需要 UAC） ----------
if (-not $SkipFirewall) {
    Write-Host ""
    Write-Host "  下一步会申请管理员权限，为 TCP $port-8796 放行入站。" -ForegroundColor Yellow
    Write-Host "  请在弹窗里点「是」，否则手机连不上。" -ForegroundColor DarkGray
    Start-Sleep -Seconds 2
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\allow-firewall.ps1")
    Start-Sleep -Seconds 2
}

# ---------- 5. 启动 ----------
if (-not $NoStart) {
    Write-Host ""
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\start.ps1")
} else {
    Write-Host ""
    Write-Host "  检查完成。双击「启动看板.bat」即可启动。" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "  安装完成。手机与电脑连同一个 Wi-Fi，打开上面打印的地址即可。" -ForegroundColor Green
Write-Host ""
Read-Host "按回车关闭"
