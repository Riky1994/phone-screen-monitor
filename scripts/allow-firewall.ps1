# PhoneDeck 防火墙放行：为 TCP 8787-8796 添加规则（端口被占时会自动顺延）
# 需要管理员权限，脚本会自己申请提权
$port = "8787-8796"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host ""
    Write-Host "  添加防火墙规则需要管理员权限。" -ForegroundColor Yellow
    Write-Host "  正在弹出授权窗口，请在窗口里点「是」..." -ForegroundColor DarkGray
    Start-Process powershell -Verb RunAs -ArgumentList `
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`""
    Start-Sleep -Seconds 3
    exit 0
}

Write-Host ""
Write-Host "  PhoneDeck - 防火墙放行" -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  正在为 TCP $port 端口添加入站规则..."

netsh advfirewall firewall delete rule name="PhoneDeck" | Out-Null
$result = netsh advfirewall firewall add rule name="PhoneDeck" dir=in action=allow protocol=TCP localport=$port profile=any
Write-Host "  $result"

Write-Host ""
Write-Host "  ---- 当前规则 ----" -ForegroundColor DarkGray
$shown = netsh advfirewall firewall show rule name="PhoneDeck" 2>&1 | Select-String -Pattern "$port|启用|Enabled|允许|Allow"
foreach ($line in $shown) { Write-Host "  $($line.ToString().Trim())" -ForegroundColor DarkGray }

Write-Host ""
Write-Host "  完成：手机现在可以访问本机的 $port 端口。" -ForegroundColor Green
Write-Host "  只放行这一段端口，不影响其它安全设置。" -ForegroundColor DarkGray
Write-Host ""
Read-Host "按回车关闭"
