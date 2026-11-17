# 提交并推送到 GitHub（SSH 方式，不需要 token）
# 用法：push.ps1              -> 用默认提交信息
#       push.ps1 "改了什么"    -> 用自定义提交信息

param([string]$Message = "")

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$git = "C:\Program Files\Git\cmd\git.exe"
if (-not (Test-Path $git)) {
    $cmd = Get-Command git -ErrorAction SilentlyContinue
    if ($cmd) { $git = $cmd.Source }
}
if (-not $git) {
    Write-Host "  找不到 git，请先安装 Git for Windows。" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

# 用 Windows 自带的 OpenSSH，避免 Git 自带的 ssh 在部分环境下握手失败
$ssh = "C:\Windows\System32\OpenSSH\ssh.exe"
if (Test-Path $ssh) {
    $env:GIT_SSH_COMMAND = "`"$ssh`" -o StrictHostKeyChecking=accept-new"
}

Write-Host ""
Write-Host "  提交并推送到 GitHub" -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor DarkGray

$remote = (& $git remote get-url origin 2>$null)
if (-not $remote) {
    Write-Host "  没有配置 origin，先手动执行：" -ForegroundColor Yellow
    Write-Host "    git remote add origin git@github.com:Riky1994/phone-screen-monitor.git" -ForegroundColor DarkGray
    Read-Host "按回车退出"
    exit 1
}
Write-Host "  远端: $remote" -ForegroundColor DarkGray

& $git add -A
$pending = (& $git status --porcelain)
if ($pending) {
    if (-not $Message) { $Message = "update: " + (Get-Date -Format "yyyy-MM-dd HH:mm") }
    & $git -c user.name="Riky" -c user.email="2523578591@qq.com" commit -m $Message | Out-Null
    Write-Host "  已提交: $Message" -ForegroundColor Green
} else {
    Write-Host "  没有新改动，直接推送" -ForegroundColor DarkGray
}

Write-Host "  正在推送..." -ForegroundColor DarkGray
& $git push origin main 2>&1 | ForEach-Object { "    $_" }

Write-Host ""
if ($LASTEXITCODE -eq 0) {
    Write-Host "  推送成功" -ForegroundColor Green
} else {
    Write-Host "  推送失败，检查网络或 SSH 密钥是否仍在 GitHub 上" -ForegroundColor Red
}
Write-Host ""
Read-Host "按回车关闭"
