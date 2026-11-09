# 启用游戏帧率：检查 RTSS，没有就引导安装
# 说明：Windows 没有系统级帧率接口，游戏帧率只能由 RTSS（MSI Afterburner 附带）
#       写进共享内存，本看板从这里读取。MSI 官网禁止程序自动下载，所以安装包
#       需要你在浏览器里下，本脚本负责检测与说明。

$ErrorActionPreference = 'Continue'

Write-Host ""
Write-Host "  启用游戏帧率（需要 RTSS）" -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor DarkGray
Write-Host ""

function Get-RtssProcess {
    return Get-Process RTSS, RTSSHooksLoader64, RTSSHooksLoader -ErrorAction SilentlyContinue | Select-Object -First 1
}

$rtss = Get-RtssProcess
$installed = @(
    "C:\Program Files (x86)\RivaTuner Statistics Server",
    "C:\Program Files\RivaTuner Statistics Server",
    "C:\Program Files (x86)\MSI Afterburner",
    "C:\Program Files\MSI Afterburner"
) | Where-Object { Test-Path $_ }

if ($rtss) {
    Write-Host "  RTSS 正在运行，帧率已经接通。" -ForegroundColor Green
    Write-Host "  进游戏后回到看板第 2 页就能看到 FPS。" -ForegroundColor Cyan
    exit 0
}

if ($installed) {
    Write-Host "  检测到已安装：" -ForegroundColor Green
    foreach ($p in $installed) { Write-Host "    $p" -ForegroundColor DarkGray }
    Write-Host ""
    Write-Host "  但 RTSS 没在后台运行。请在开始菜单打开 " -ForegroundColor Yellow
    Write-Host "  「RivaTuner Statistics Server」，让它常驻托盘，然后重跑本脚本。" -ForegroundColor Yellow
    exit 0
}

Write-Host "  还没有安装。安装后还需要 RTSS 常驻后台才能取到帧率。" -ForegroundColor Yellow
Write-Host ""
Write-Host "  步骤：" -ForegroundColor Cyan
Write-Host "    1. 浏览器会打开 MSI Afterburner 官方下载页"
Write-Host "    2. 下载并安装，安装过程中务必勾选 " -NoNewline
Write-Host "RivaTuner Statistics Server" -ForegroundColor Yellow
Write-Host "    3. 装完让 RTSS 在后台运行（托盘有个粉色小图标）"
Write-Host "    4. 进游戏，看板第 2 页的帧率就会自动显示"
Write-Host ""

Start-Process "https://www.msi.com/Landing/afterburner/graphics-cards"

Write-Host "  已打开下载页。装好并启动 RTSS 后，等 2 分钟..." -ForegroundColor DarkGray
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 2
    if (Get-RtssProcess) {
        Write-Host ""
        Write-Host "  检测到 RTSS 已在运行，帧率接通！" -ForegroundColor Green
        Write-Host "  回到看板第 2 页即可看到 FPS。" -ForegroundColor Cyan
        exit 0
    }
}

Write-Host ""
Write-Host "  暂时还没检测到 RTSS。装好并启动它之后，直接回看板刷新即可，" -ForegroundColor DarkGray
Write-Host "  不需要再跑这个脚本。" -ForegroundColor DarkGray
