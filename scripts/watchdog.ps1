# PhoneDeck 守护：检查服务是否活着，掉了就拉起来，并记录一条日志
# 由计划任务每 3 分钟调用一次；手动跑也行。

$root = Split-Path -Parent $PSScriptRoot
$log = Join-Path $root "logs\server.log"

function Write-Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    try { Add-Content -Path $log -Value $line -Encoding UTF8 } catch {}
}

$alive = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8787/health" -UseBasicParsing -TimeoutSec 4
    $alive = ($r.StatusCode -eq 200)
} catch { $alive = $false }

if ($alive) { exit 0 }

Write-Log "守护：检测到服务未运行，正在重启"
$start = Join-Path $root "scripts\start.ps1"
try {
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$start`"", "-NoBrowser" `
        -WindowStyle Hidden
    Start-Sleep -Seconds 12
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8787/health" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200) { Write-Log "守护：重启成功" }
    else { Write-Log "守护：重启后仍无响应" }
} catch {
    Write-Log ("守护：重启失败 - " + $_.Exception.Message)
}
