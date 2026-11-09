# PhoneDeck 移除开机自启
$ErrorActionPreference = 'Stop'
try {
    $startup = [Environment]::GetFolderPath('Startup')
    $lnk = Join-Path $startup 'PhoneDeck.lnk'
    if (Test-Path $lnk) {
        Remove-Item $lnk -Force
        Write-Host ""
        Write-Host "  已移除开机自启。" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "  没有安装过开机自启，无需操作。" -ForegroundColor DarkGray
    }
    exit 0
} catch {
    Write-Host ""
    Write-Host "  [失败] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
