# PhoneDeck 停止器：读取 pid 文件并结束进程
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root "logs\server.pid"

if (-not (Test-Path $pidFile)) {
    Write-Host "  没有找到运行记录，服务可能并没有在运行。" -ForegroundColor DarkGray
    exit 0
}

$target = (Get-Content $pidFile -Raw -ErrorAction SilentlyContinue)
if ($target) { $target = $target.Trim() }
if ($target -notmatch '^\d+$') {
    Write-Host "  运行记录无效，已清理。" -ForegroundColor DarkGray
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    exit 0
}

$prev = Get-Process -Id ([int]$target) -ErrorAction SilentlyContinue
if (-not $prev) {
    Write-Host "  进程 $target 已经退出了。" -ForegroundColor DarkGray
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    exit 0
}
if ($prev.ProcessName -notlike 'python*') {
    Write-Host "  记录里的 PID $target 现在被 $($prev.ProcessName) 占用，不是看板进程，已跳过。" -ForegroundColor Yellow
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    exit 0
}

try {
    Stop-Process -Id ([int]$target) -Force -ErrorAction Stop
    Write-Host "  已停止看板服务（PID $target）。" -ForegroundColor Green
} catch {
    Write-Host "  停止失败：$($_.Exception.Message)" -ForegroundColor Yellow
}
Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
