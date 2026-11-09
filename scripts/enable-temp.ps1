# 启用 CPU 温度：启动 LibreHardwareMonitor 并确认网页服务已开启
# 说明：LHM 需要管理员权限才能加载传感器驱动，所以必然会弹出一次 UAC；
#       它的网页服务默认关闭，需要在菜单里点一次「Run」，之后会记住。

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$lhmDir = Join-Path $root "tools\LibreHardwareMonitor"
$exe = Join-Path $lhmDir "LibreHardwareMonitor.exe"

function Test-Lhm {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8085/data.json" -UseBasicParsing -TimeoutSec 1
        return $r.StatusCode -eq 200
    } catch { return $false }
}

Write-Host ""
Write-Host "  启用 CPU 温度（LibreHardwareMonitor）" -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor DarkGray
Write-Host ""

if (Test-Lhm) {
    Write-Host "  已经在运行了，温度数据已接通。" -ForegroundColor Green
    Write-Host "  回到手机看板刷新一下即可。" -ForegroundColor DarkGray
    exit 0
}

# 没装就自动下载
if (-not (Test-Path $exe)) {
    Write-Host "  本地没有 LibreHardwareMonitor，正在下载（约 6 MB）..." -ForegroundColor DarkGray
    $zip = Join-Path $env:TEMP "LibreHardwareMonitor.zip"
    try {
        Invoke-WebRequest -Uri "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/latest/download/LibreHardwareMonitor.zip" -OutFile $zip -UseBasicParsing -TimeoutSec 120
        New-Item -ItemType Directory -Force -Path $lhmDir | Out-Null
        Expand-Archive -Path $zip -DestinationPath $lhmDir -Force
        Remove-Item $zip -Force -ErrorAction SilentlyContinue
        Write-Host "  下载完成。" -ForegroundColor Green
    } catch {
        Write-Host "  [失败] 下载出错：$($_.Exception.Message)" -ForegroundColor Red
        Write-Host "  可以手动下载后解压到：$lhmDir" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "  即将以管理员身份启动 LibreHardwareMonitor。" -ForegroundColor Yellow
Write-Host "  请在 UAC 弹窗里点「是」。" -ForegroundColor Yellow
Write-Host ""
Start-Sleep -Seconds 1
Start-Process -FilePath $exe -WorkingDirectory $lhmDir -Verb RunAs

Write-Host "  等待它启动..." -ForegroundColor DarkGray
$hinted = $false
for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 2
    if (Test-Lhm) {
        Write-Host ""
        Write-Host "  成功！温度、风扇、CPU 功耗已经接通。" -ForegroundColor Green
        Write-Host "  回到手机看板刷新一下就能看到数字了。" -ForegroundColor Cyan
        Write-Host "  以后开机只要 LHM 在后台开着就行（可以最小化到托盘）。" -ForegroundColor DarkGray
        exit 0
    }
    if (-not $hinted -and $i -ge 3) {
        $hinted = $true
        Write-Host ""
        Write-Host "  还需要你点一下：在 LibreHardwareMonitor 窗口菜单里" -ForegroundColor Yellow
        Write-Host "    Options  ->  Remote Web Server  ->  Run" -ForegroundColor Yellow
        Write-Host "  点完这个脚本会自动检测到（只需要设置一次，它会记住）。" -ForegroundColor DarkGray
        Write-Host ""
    }
}

Write-Host ""
Write-Host "  还没有检测到 8085 端口。" -ForegroundColor Yellow
Write-Host "  如果 LHM 已经开着，请确认菜单里 Remote Web Server 处于勾选状态。" -ForegroundColor DarkGray
Write-Host "  设置好后回到手机看板刷新即可，不必重跑本脚本。" -ForegroundColor DarkGray
