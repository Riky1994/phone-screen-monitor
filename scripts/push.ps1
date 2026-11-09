# 上传到 GitHub：输入仓库地址 -> 设置 origin -> push
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$git = "C:\Program Files\Git\cmd\git.exe"
if (-not (Test-Path $git)) {
    $cmd = Get-Command git -ErrorAction SilentlyContinue
    if ($cmd) { $git = $cmd.Source }
}
if (-not $git -or -not (Test-Path $git)) {
    Write-Host "  找不到 git，请先安装 Git for Windows。" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

Write-Host ""
Write-Host "  上传 skill 包到 GitHub" -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  1) 先在浏览器里新建一个空仓库（不要勾 README / .gitignore / License）" -ForegroundColor DarkGray
Write-Host "  2) 复制它页面上 HTTPS 那一行的地址，粘贴到下面" -ForegroundColor DarkGray
Write-Host ""

$url = Read-Host "  仓库地址 (形如 https://github.com/Riky1994/手机屏监控电脑性能.git)"
if (-not $url) {
    Write-Host "  没有输入地址，已取消。" -ForegroundColor Yellow
    Read-Host "按回车退出"
    exit 1
}
$url = $url.Trim()

& $git remote remove origin 2>$null | Out-Null
& $git remote add origin $url

Write-Host ""
Write-Host "  正在推送，稍等..." -ForegroundColor DarkGray
& $git push -u origin main

Write-Host ""
if ($LASTEXITCODE -eq 0) {
    Write-Host "  推送成功！仓库地址：" -ForegroundColor Green
    Write-Host "  $($url -replace '\.git$','')" -ForegroundColor Cyan
} else {
    Write-Host "  推送失败。常见原因：" -ForegroundColor Yellow
    Write-Host "    - 地址贴错（要 .git 结尾的那个 HTTPS 地址）" -ForegroundColor DarkGray
    Write-Host "    - 浏览器授权窗口被关掉了：重新运行本脚本，在弹窗里点 Authorize" -ForegroundColor DarkGray
    Write-Host "    - 如果提示要输入密码，把 GitHub 的 token 粘贴进去即可" -ForegroundColor DarkGray
}
Write-Host ""
Read-Host "按回车关闭"
