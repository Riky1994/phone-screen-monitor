# PhoneDeck 启动器：结束旧实例 -> 定位 Python -> 后台启动 -> 健康检查 -> 打开浏览器
# 兼容本机 DSH 自带运行时 / 系统 Python / py 启动器，换机器也能跑
param([switch]$NoBrowser)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$port = 8787

Write-Host ""
Write-Host "  PhoneDeck - 手机性能看板" -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor DarkGray
Write-Host ""

# 1. 结束上一个实例
$pidFile = Join-Path $root "logs\server.pid"
if (Test-Path $pidFile) {
    $old = (Get-Content $pidFile -Raw -ErrorAction SilentlyContinue)
    if ($old) { $old = $old.Trim() }
    if ($old -match '^\d+$') {
        $prev = Get-Process -Id ([int]$old) -ErrorAction SilentlyContinue
        if ($prev -and $prev.ProcessName -like 'python*') {
            Stop-Process -Id ([int]$old) -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 900
        }
    }
}

# 1b. 按端口占用者接管：pid 文件可能失效，但旧实例仍占着端口
try {
    $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listeners) {
        foreach ($l in $listeners) {
            $ownerId = $l.OwningProcess
            if (-not $ownerId -or $ownerId -eq 0) { continue }
            $owner = Get-Process -Id $ownerId -ErrorAction SilentlyContinue
            if ($owner -and $owner.ProcessName -like 'python*') {
                Stop-Process -Id $ownerId -Force -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Milliseconds 800
    }
} catch { }

# 2. 定位 Python：优先 DSH 自带运行时，其次系统 Python，最后 py 启动器
$pyw = $null
$runtimeRoot = Join-Path $env:USERPROFILE ".dsh\dsh-runtimes"
if (Test-Path $runtimeRoot) {
    $pyw = Get-ChildItem -Path $runtimeRoot -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName "dependencies\python\pythonw.exe" } |
        Where-Object { Test-Path $_ } |
        Select-Object -First 1
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
    Write-Host "  [错误] 没找到可用的 Python（pythonw.exe / python.exe / pyw.exe）。" -ForegroundColor Red
    Write-Host "  请先安装 Python 3.9+（勾选 Add to PATH），或修改 scripts\start.ps1。" -ForegroundColor DarkGray
    Read-Host "按回车退出"
    exit 1
}

Write-Host "  使用 Python: $pyw" -ForegroundColor DarkGray
Write-Host "  正在启动服务..."
Start-Process -FilePath $pyw -ArgumentList "server.py" -WorkingDirectory $root -WindowStyle Hidden

# 3. 健康检查
$ok = $false
for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Milliseconds 600
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$port/health" -UseBasicParsing -TimeoutSec 1
        if ($resp.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
}

$url = "http://127.0.0.1:$port"
$addrFile = Join-Path $root "address.txt"
if (Test-Path $addrFile) {
    $tmp = (Get-Content $addrFile -Raw -ErrorAction SilentlyContinue)
    if ($tmp) { $tmp = $tmp.Trim() }
    if ($tmp) { $url = $tmp }
}

Write-Host ""
if (-not $ok) {
    Write-Host "  [警告] 服务没能启动，最近日志：" -ForegroundColor Yellow
    $log = Join-Path $root "logs\server.log"
    if (Test-Path $log) {
        Get-Content $log -Tail 8 -Encoding UTF8 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    }
    Read-Host "按回车退出"
    exit 1
}

Write-Host "  电脑浏览器: http://127.0.0.1:$port"
Write-Host "  手机浏览器: $url" -ForegroundColor Cyan
Write-Host ""
Write-Host "  手机和电脑要连同一个路由器 / Wi-Fi" -ForegroundColor DarkGray
Write-Host "  第一次使用请先双击「允许手机访问.bat」放行防火墙" -ForegroundColor DarkGray
Write-Host ""

Start-Sleep -Milliseconds 500
if (-not $NoBrowser) { Start-Process $url }
Start-Sleep -Seconds 2
